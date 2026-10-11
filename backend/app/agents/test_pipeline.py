"""Grok reads the words, code decides, and GPT writes only the kept market slices."""

from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from app.agents.catalog import (
    DEFAULT_ANALYST_MODEL,
    DEFAULT_INTAKE_MODEL,
    HIGH_EFFORT,
    TaskModels,
    resolve_tasks,
    specs_by_id,
)
from app.agents.client import Completion, GatewayClient, completion_request
from app.agents.pipeline import analyze_run, execute_analyze
from app.market.cli import build_parser
from app.market.validate import CitationError

HALE = Path(__file__).resolve().parents[3] / "data/market/hale/20261011T000403Z"
GOAL = "I need about $5 million I can reach within three years to start a company."
INTENT = "Five million he can reach."


def task_models() -> TaskModels:
    return TaskModels(
        intake_model=DEFAULT_INTAKE_MODEL,
        intake_effort=HIGH_EFFORT,
        analyst_model=DEFAULT_ANALYST_MODEL,
        analyst_effort=HIGH_EFFORT,
    )


def catalog_row(model_id: str, efforts: list[str], structured: bool = True) -> dict:
    return {
        "id": model_id,
        "reasoning_options": [{"type": "effort", "values": efforts}],
        "tags": ["structured-output"] if structured else [],
        "supported_parameters": [],
    }


def default_catalog() -> list[dict]:
    return [
        catalog_row(DEFAULT_INTAKE_MODEL, ["low", "medium", "high", "xhigh"]),
        catalog_row(DEFAULT_ANALYST_MODEL, ["none", "low", "medium", "high", "xhigh"]),
    ]


class FakeClient:
    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.calls: list[dict] = []

    def complete(self, *, task, model, effort, messages, schema_name, schema) -> Completion:
        del schema
        self.calls.append(
            {"task": task, "model": model, "effort": effort, "messages": messages, "schema_name": schema_name}
        )
        return Completion(
            text=self.replies.pop(0),
            model=model,
            effort=effort,
            prompt_tokens=11,
            completion_tokens=7,
            total_tokens=18,
        )


def brief_reply(
    *,
    amount: float | None,
    slices: list[str],
    decisions: list[str] | None = None,
    intent: str = INTENT,
) -> str:
    return json.dumps(
        {
            "amount_usd": amount,
            "horizon": "three years",
            "intent": intent,
            "slices": slices,
            "decisions": decisions or [],
            "ambiguous": False,
        }
    )


def report_reply(evidence_id: str = "yahoo:SPY", url: str = "https://finance.yahoo.com/quote/SPY") -> str:
    return json.dumps(
        {
            "score": 40,
            "gap_usd": 2749999.97,
            "verdict": "Cash on hand is short of the goal.",
            "discrepancies": [
                {
                    "claim": "Cash he can reach is short of the goal.",
                    "severity": "high",
                    "evidence_ids": [evidence_id],
                }
            ],
            "meeting_agenda": ["Show the cash gap."],
            "source_urls": [url],
        }
    )


def fill(directory: Path) -> None:
    for name in ("evidence.json", "facts.json"):
        (directory / name).write_text((HALE / name).read_text())


def user_text(call: dict) -> str:
    return call["messages"][-1]["content"]


class CatalogTests(unittest.TestCase):
    def test_defaults_are_grok_and_gpt_at_high_effort(self) -> None:
        tasks = resolve_tasks(default_catalog(), {})
        self.assertEqual(tasks.intake_model, "spacexai/grok-4.7")
        self.assertEqual(tasks.analyst_model, "openai/gpt-5.5")
        self.assertEqual(tasks.intake_effort, "high")
        self.assertEqual(tasks.analyst_effort, "high")
        self.assertNotEqual(tasks.intake_effort, "xhigh")
        self.assertNotEqual(tasks.analyst_effort, "xhigh")

    def test_empty_override_keeps_the_defaults(self) -> None:
        tasks = resolve_tasks(default_catalog(), {"AGENT_TRIAGE_MODEL": "", "AGENT_ANALYST_MODEL": ""})
        self.assertEqual(tasks.intake_model, DEFAULT_INTAKE_MODEL)
        self.assertEqual(tasks.analyst_model, DEFAULT_ANALYST_MODEL)

    def test_model_without_high_effort_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            resolve_tasks(
                [catalog_row("small/no-high", ["low", "medium"]), catalog_row(DEFAULT_ANALYST_MODEL, ["high"])],
                {"AGENT_TRIAGE_MODEL": "small/no-high"},
            )
        with self.assertRaises(ValueError):
            resolve_tasks(
                [catalog_row(DEFAULT_INTAKE_MODEL, ["high"]), catalog_row("mid/no-high", ["medium"])],
                {"AGENT_ANALYST_MODEL": "mid/no-high"},
            )

    def test_request_sets_high_effort_and_leaves_reasoning_out_of_the_response(self) -> None:
        request = completion_request("openai/gpt-5.5", "high", [], "alignment_report", {"type": "object"})
        self.assertEqual(request["extra_body"]["reasoning"], {"effort": "high", "exclude": True})
        self.assertEqual(request["response_format"]["json_schema"]["name"], "alignment_report")

    def test_client_rejects_an_effort_before_calling_the_gateway(self) -> None:
        specs = specs_by_id([catalog_row(DEFAULT_ANALYST_MODEL, ["medium"])])
        client = GatewayClient("test-key", specs)
        with self.assertRaises(ValueError):
            client.complete(
                task="analyst",
                model=DEFAULT_ANALYST_MODEL,
                effort="high",
                messages=[],
                schema_name="alignment_report",
                schema={"type": "object"},
            )


class PipelineTests(unittest.TestCase):
    def test_empty_goal_makes_no_model_call(self) -> None:
        fake = FakeClient([])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = analyze_run(root, "  ", fake, task_models())
            self.assertTrue(result.trace.stopped)
            self.assertEqual(result.trace.calls, [])
            self.assertFalse((root / "alignment.json").exists())
            self.assertIn("No goal", (root / "triage.json").read_text())

    def test_no_amount_never_calls_the_analyst(self) -> None:
        fake = FakeClient([brief_reply(amount=None, slices=[])])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fill(root)
            (root / "alignment.json").write_text("{}\n")
            result = analyze_run(root, GOAL, fake, task_models())
            self.assertFalse((root / "alignment.json").exists())
            self.assertFalse((root / "alert.json").exists())
            self.assertIn("no amount", (root / "triage.json").read_text())
        self.assertEqual([call["task"] for call in fake.calls], ["intake"])
        self.assertTrue(result.trace.stopped)
        self.assertEqual(result.trace.calls[0].effort, "high")
        self.assertEqual(result.trace.calls[0].model, DEFAULT_INTAKE_MODEL)

    def test_cash_that_already_covers_the_need_stops(self) -> None:
        fake = FakeClient([brief_reply(amount=1000, slices=["quotes", "funding"])])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fill(root)
            result = analyze_run(root, GOAL, fake, task_models())
        self.assertEqual([call["task"] for call in fake.calls], ["intake"])
        self.assertTrue(result.trace.stopped)
        self.assertIn("Cash already covers", result.triage.reason)

    def test_models_do_not_read_the_same_material(self) -> None:
        fake = FakeClient(
            [brief_reply(amount=5_000_000, slices=["quotes"], decisions=["Bought VNQ for income."]), report_reply()]
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fill(root)
            (root / "notes.txt").write_text("FENWICK-NOTE-BODY He bought the real-estate fund for income.")
            result = analyze_run(root, GOAL, fake, task_models())
            trace = json.loads((root / "pipeline.json").read_text())
            alert = json.loads((root / "alert.json").read_text())
        intake_body = user_text(fake.calls[0])
        analyst_body = user_text(fake.calls[1])
        self.assertIn("start a company", intake_body)
        self.assertIn("FENWICK-NOTE-BODY", intake_body)
        self.assertNotIn("629.28", intake_body)
        self.assertNotIn("48000000", intake_body)
        self.assertNotIn("2250000", intake_body)
        self.assertNotIn("a&g eirl", intake_body)
        self.assertIn("629.28", analyst_body)
        self.assertIn(INTENT, analyst_body)
        self.assertIn("Bought VNQ for income.", analyst_body)
        self.assertNotIn("start a company", analyst_body)
        self.assertNotIn("FENWICK-NOTE-BODY", analyst_body)
        self.assertNotIn("48000000", analyst_body)
        self.assertNotIn("a&g eirl", analyst_body)
        self.assertNotIn("live_price", analyst_body)
        self.assertNotIn("omitted:home", analyst_body)
        self.assertEqual([call["effort"] for call in fake.calls], ["high", "high"])
        self.assertEqual(fake.calls[0]["model"], DEFAULT_INTAKE_MODEL)
        self.assertEqual(fake.calls[1]["model"], DEFAULT_ANALYST_MODEL)
        self.assertEqual([call["task"] for call in trace["calls"]], ["intake", "analyst"])
        self.assertEqual(trace["calls"][0]["prompt_tokens"], 11)
        self.assertEqual(trace["stopped"], False)
        self.assertEqual(alert["severity"], "high")
        self.assertEqual(result.report.score, 40)

    def test_bad_citation_is_retried_once_at_the_same_effort(self) -> None:
        fake = FakeClient(
            [
                brief_reply(amount=5_000_000, slices=["quotes"]),
                report_reply("yahoo:NOT-A-TICKER", "https://example.com/invented"),
                report_reply(),
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fill(root)
            analyze_run(root, GOAL, fake, task_models())
            self.assertTrue((root / "alignment.json").exists())
        analyst_calls = [call for call in fake.calls if call["task"] == "analyst"]
        self.assertEqual(len(analyst_calls), 2)
        self.assertEqual([call["effort"] for call in analyst_calls], ["high", "high"])
        self.assertIn("unknown evidence ids", user_text(analyst_calls[1]))

    def test_second_citation_failure_stops_without_a_report(self) -> None:
        fake = FakeClient(
            [
                brief_reply(amount=5_000_000, slices=["quotes"]),
                report_reply("yahoo:NOT-A-TICKER", "https://example.com/invented"),
                report_reply("yahoo:ALSO-MISSING", "https://example.com/still-invented"),
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fill(root)
            with self.assertRaises(CitationError):
                analyze_run(root, GOAL, fake, task_models())
            self.assertFalse((root / "alignment.json").exists())
            self.assertFalse((root / "alert.json").exists())
            trace = json.loads((root / "pipeline.json").read_text())
        self.assertEqual([call["task"] for call in trace["calls"]], ["intake", "analyst", "analyst"])
        self.assertTrue(trace["stopped"])

    def test_analyze_command_reads_goal_txt(self) -> None:
        fake = FakeClient([brief_reply(amount=None, slices=[])])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fill(root)
            (root / "goal.txt").write_text(GOAL)
            with redirect_stdout(StringIO()):
                execute_analyze(root, None, client=fake, tasks=task_models())
        self.assertIn("5 million", user_text(fake.calls[0]))
        args = build_parser().parse_args(["analyze", str(root), "--goal", GOAL])
        self.assertEqual(args.command, "analyze")
        self.assertEqual(args.goal, GOAL)


if __name__ == "__main__":
    unittest.main()
