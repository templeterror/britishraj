"""Intake asks until the goal is specific, code builds the tree, the analyst explains, code routes, the advisor writes."""

from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from app.agents.advisor import route
from app.agents.catalog import DEFAULT_MODEL, HIGH_EFFORT, TaskModels, resolve_tasks
from app.agents.checks import build_tree
from app.agents.client import Completion, XaiClient, completion_request, json_schema
from app.agents.intake import MAX_QUESTIONS
from app.agents.pipeline import analyze_run, converse, execute_analyze, load_conversation
from app.agents.schemas import DecisionTree, GoalBrief
from app.market.cli import build_parser
from app.market.schemas import LiquidityFacts, MarketEvidence
from app.market.validate import CitationError, validate_run

HALE = Path(__file__).resolve().parents[3] / "data/market/hale/20261011T000403Z"
VAGUE = "I want to start a technology company."
SPECIFIC = "About five million I can actually reach, within three years, not money tied up in real estate."
INTENT = "Start a technology company with money he can reach."
NOTE = "FENWICK-NOTE-BODY He bought the real-estate fund for income."


def task_models() -> TaskModels:
    return resolve_tasks({})


class FakeClient:
    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.calls: list[dict] = []

    def complete(self, *, task, model, effort, messages, schema_name, schema) -> Completion:
        del schema
        self.calls.append(
            {"task": task, "model": model, "effort": effort, "messages": messages, "schema_name": schema_name}
        )
        if not self.replies:
            raise AssertionError(f"unexpected {task} call")
        return Completion(
            text=self.replies.pop(0),
            model=model,
            effort=effort,
            prompt_tokens=11,
            completion_tokens=7,
            total_tokens=18,
        )

    def tasks(self) -> list[str]:
        return [call["task"] for call in self.calls]


def intake_reply(
    *,
    amount: float | None = None,
    horizon: int | None = None,
    purpose: str | None = None,
    question: str | None = None,
    decisions: list[str] | None = None,
    reachable: bool = True,
    exclusions: list[str] | None = None,
) -> str:
    return json.dumps(
        {
            "brief": {
                "intent": INTENT,
                "amount_usd": amount,
                "amount_is_estimate": True,
                "horizon_months": horizon,
                "purpose": purpose,
                "must_be_reachable": reachable,
                "exclusions": exclusions if exclusions is not None else ["money tied up in real estate"],
                "decisions": decisions or [],
                "slices": [],
                "missing": [],
            },
            "question": question,
        }
    )


def analyst_reply(tree: DecisionTree, *, bad_id: str | None = None, skip: str | None = None, url: str | None = None) -> str:
    findings = []
    judgments = []
    for node in tree.nodes():
        if node.outcome == "skipped" or node.id == skip:
            continue
        ids = list(node.evidence_ids)
        if bad_id and node.id == "cash":
            ids = [bad_id]
        if node.outcome == "pending":
            judgments.append(
                {
                    "node_id": node.id,
                    "outcome": "misaligned",
                    "severity": "low",
                    "finding": "The real-estate fund was bought for income, which pulls against reachable cash.",
                    "evidence_ids": ids,
                }
            )
            continue
        findings.append({"node_id": node.id, "finding": f"Finding for {node.id}.", "evidence_ids": ids})
    return json.dumps(
        {
            "findings": findings,
            "judgments": judgments,
            "verdict": "Cash is short and the book leans on real estate.",
            "meeting_agenda": ["Read the goal back.", "Show the cash gap.", "Walk through the liquid funds."],
            "source_urls": [url] if url else ["https://finance.yahoo.com/quote/SPY"],
        }
    )


def advisor_reply() -> str:
    return json.dumps(
        {
            "headline": "James needs reachable cash the book does not hold",
            "why": "Cash is short and most of the book is real estate he said does not count.",
            "next_actions": ["Ask Robert why the real-estate sleeve grew.", "Ask James whether the horizon can move."],
        }
    )


def fill(directory: Path, notes: bool = False) -> None:
    for name in ("evidence.json", "facts.json"):
        (directory / name).write_text((HALE / name).read_text())
    if notes:
        (directory / "notes.txt").write_text(NOTE)


def hale_tree(brief: GoalBrief, status: str = "ready") -> DecisionTree:
    facts = LiquidityFacts.model_validate_json((HALE / "facts.json").read_text())
    evidence = MarketEvidence.model_validate_json((HALE / "evidence.json").read_text())
    return build_tree(brief, status, facts, evidence)


def specific_brief(**overrides) -> GoalBrief:
    base = dict(
        intent=INTENT,
        amount_usd=5_000_000,
        amount_is_estimate=True,
        horizon_months=36,
        purpose="company",
        must_be_reachable=True,
        exclusions=["money tied up in real estate"],
        slices=["quotes", "funding"],
    )
    base.update(overrides)
    return GoalBrief(**base)


def user_text(call: dict) -> str:
    return call["messages"][-1]["content"]


def flatten(node: dict) -> list[dict]:
    rows = [node]
    for child in node["children"]:
        rows.extend(flatten(child))
    return rows


class CatalogTests(unittest.TestCase):
    def test_every_agent_defaults_to_grok_at_high_effort(self) -> None:
        tasks = resolve_tasks({})
        self.assertEqual((tasks.intake_model, tasks.analyst_model, tasks.advisor_model), ("grok-4.7",) * 3)
        self.assertEqual((tasks.intake_effort, tasks.analyst_effort, tasks.advisor_effort), ("high",) * 3)

    def test_empty_override_keeps_the_defaults(self) -> None:
        tasks = resolve_tasks({"AGENT_INTAKE_MODEL": "", "AGENT_ANALYST_MODEL": "", "AGENT_ADVISOR_MODEL": ""})
        self.assertEqual(tasks.intake_model, DEFAULT_MODEL)
        self.assertEqual(tasks.advisor_model, DEFAULT_MODEL)

    def test_advisor_follows_the_analyst_unless_named(self) -> None:
        tasks = resolve_tasks({"AGENT_ANALYST_MODEL": "grok-4.6"})
        self.assertEqual(tasks.advisor_model, "grok-4.6")
        tasks = resolve_tasks({"AGENT_ANALYST_MODEL": "grok-4.6", "AGENT_ADVISOR_MODEL": "grok-4.5"})
        self.assertEqual(tasks.advisor_model, "grok-4.5")

    def test_unknown_model_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            resolve_tasks({"AGENT_INTAKE_MODEL": "openai/gpt-5.5"})

    def test_request_sets_high_effort_and_a_strict_schema(self) -> None:
        request = completion_request("grok-4.7", "high", [], "analyst_reply", {"type": "object"})
        self.assertEqual(request["reasoning_effort"], "high")
        self.assertEqual(request["response_format"]["json_schema"]["name"], "analyst_reply")
        self.assertTrue(request["response_format"]["json_schema"]["strict"])
        self.assertNotIn("extra_body", request)

    def test_schema_is_strict_all_the_way_down(self) -> None:
        schema = json_schema(GoalBrief)
        self.assertEqual(sorted(schema["required"]), sorted(schema["properties"]))
        self.assertFalse(schema["additionalProperties"])
        self.assertNotIn("title", schema)
        self.assertNotIn("default", schema["properties"]["amount_usd"])
        self.assertEqual(schema["properties"]["purpose"]["anyOf"][1], {"type": "null"})

    def test_client_rejects_a_bad_effort_before_calling_xai(self) -> None:
        client = XaiClient("test-key")
        with self.assertRaises(ValueError):
            client.complete(
                task="analyst",
                model="grok-4.5",
                effort="xhigh",
                messages=[],
                schema_name="analyst_reply",
                schema={"type": "object"},
            )


class IntakeTests(unittest.TestCase):
    def test_vague_goal_gets_one_question_and_no_analysis(self) -> None:
        fake = FakeClient([intake_reply(purpose="company", question="Roughly how much would that take?")])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fill(root)
            conversation, _ = converse(root, VAGUE, fake, task_models())
            self.assertEqual(conversation.status, "asking")
            self.assertEqual([m.role for m in conversation.messages], ["heir", "agent"])
            self.assertEqual(conversation.messages[-1].text, "Roughly how much would that take?")
            self.assertEqual(conversation.brief.missing, ["amount", "horizon"])
            result = analyze_run(root, fake, task_models())
            self.assertTrue(result.trace.stopped)
            self.assertIn("still asking", result.trace.reason)
            self.assertFalse((root / "decision.json").exists())
        self.assertEqual(fake.tasks(), ["intake"])

    def test_intake_sees_words_and_notes_but_no_numbers(self) -> None:
        fake = FakeClient([intake_reply(question="How much?")])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fill(root, notes=True)
            converse(root, VAGUE, fake, task_models())
        body = user_text(fake.calls[0])
        self.assertIn(VAGUE, body)
        self.assertIn("FENWICK-NOTE-BODY", body)
        self.assertNotIn("629.28", body)
        self.assertNotIn("2250000", body)
        self.assertEqual(fake.calls[0]["model"], DEFAULT_MODEL)
        self.assertEqual(fake.calls[0]["effort"], "high")

    def test_second_answer_settles_the_goal_and_drops_the_question(self) -> None:
        fake = FakeClient(
            [
                intake_reply(purpose="company", question="How much?"),
                intake_reply(amount=5_000_000, horizon=36, purpose="company", question="Anything else?"),
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            converse(root, VAGUE, fake, task_models())
            conversation, _ = converse(root, SPECIFIC, fake, task_models())
            saved = load_conversation(root)
        self.assertEqual(conversation.status, "ready")
        self.assertEqual([m.role for m in conversation.messages], ["heir", "agent", "heir"])
        self.assertEqual(conversation.brief.slices, ["quotes", "funding"])
        self.assertEqual(conversation.brief.missing, [])
        self.assertEqual(saved, conversation)
        transcript = json.loads(user_text(fake.calls[1]))["transcript"]
        self.assertEqual([m["role"] for m in transcript], ["heir", "agent", "heir"])

    def test_purpose_alone_is_asked_but_never_blocks(self) -> None:
        fake = FakeClient([intake_reply(amount=5_000_000, horizon=36, question="What is it for?")] * 4)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            conversation, _ = converse(root, SPECIFIC, fake, task_models())
            self.assertEqual(conversation.status, "asking")
            self.assertEqual(conversation.brief.missing, ["purpose"])
            for _ in range(MAX_QUESTIONS):
                conversation, _ = converse(root, "I would rather not say.", fake, task_models())
        self.assertEqual(conversation.status, "ready")
        self.assertEqual(conversation.brief.slices, ["quotes"])

    def test_three_questions_then_proceed_with_gaps(self) -> None:
        fake = FakeClient([intake_reply(question="How much?")] * (MAX_QUESTIONS + 1))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            conversation, _ = converse(root, VAGUE, fake, task_models())
            for _ in range(MAX_QUESTIONS):
                conversation, _ = converse(root, "I am not sure.", fake, task_models())
        self.assertEqual(conversation.status, "ready_with_gaps")
        self.assertEqual(conversation.questions_asked, MAX_QUESTIONS)
        self.assertEqual(sum(1 for m in conversation.messages if m.role == "agent"), MAX_QUESTIONS)

    def test_empty_question_falls_back_to_a_plain_one(self) -> None:
        fake = FakeClient([intake_reply(question="")])
        with tempfile.TemporaryDirectory() as tmp:
            conversation, _ = converse(Path(tmp), VAGUE, fake, task_models())
        self.assertEqual(conversation.messages[-1].text, "Roughly how much money would this take?")

    def test_a_settled_conversation_starts_over_on_the_next_message(self) -> None:
        fake = FakeClient(
            [
                intake_reply(amount=5_000_000, horizon=36, purpose="company"),
                intake_reply(question="How much?"),
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            converse(root, SPECIFIC, fake, task_models())
            conversation, _ = converse(root, VAGUE, fake, task_models())
        self.assertEqual([m.text for m in conversation.messages if m.role == "heir"], [VAGUE])


class CheckTests(unittest.TestCase):
    def test_hale_tree_matches_the_numbers(self) -> None:
        tree = hale_tree(specific_brief())
        by_id = {node.id: node for node in tree.nodes()}
        self.assertEqual(by_id["goal"].outcome, "aligned")
        self.assertEqual((by_id["cash"].outcome, by_id["cash"].severity), ("misaligned", "high"))
        self.assertIn("$2,749,999.97", by_id["cash"].detail)
        self.assertEqual(by_id["liquid"].outcome, "aligned")
        self.assertIn("2.89 times", by_id["liquid"].detail)
        self.assertEqual(by_id["horizon"].outcome, "aligned")
        self.assertEqual((by_id["concentration"].outcome, by_id["concentration"].severity), ("misaligned", "medium"))
        self.assertIn("62.8%", by_id["concentration"].detail)
        self.assertEqual(by_id["purpose"].outcome, "gap")
        self.assertNotIn("home", by_id)
        self.assertNotIn("notes", by_id)
        self.assertEqual(tree.score, 50)
        self.assertEqual(by_id["cash"].evidence_ids, ["yahoo:VMFXX"])
        self.assertEqual(sorted(by_id["liquid"].evidence_ids), ["yahoo:MUB", "yahoo:SPY", "yahoo:TLT"])

    def test_cash_that_covers_the_amount_skips_the_liquidity_branch(self) -> None:
        tree = hale_tree(specific_brief(amount_usd=1_000))
        by_id = {node.id: node for node in tree.nodes()}
        self.assertEqual(by_id["cash"].outcome, "aligned")
        self.assertEqual(by_id["liquid"].outcome, "skipped")
        self.assertEqual(by_id["horizon"].outcome, "skipped")
        self.assertEqual(route(tree)[0], "review")

    def test_no_exclusion_leaves_concentration_aligned(self) -> None:
        tree = hale_tree(specific_brief(amount_usd=1_000, must_be_reachable=False, exclusions=[]))
        by_id = {node.id: node for node in tree.nodes()}
        self.assertEqual(by_id["concentration"].outcome, "aligned")
        self.assertEqual(tree.score, 100)
        self.assertEqual(route(tree), ("none", "Every check is aligned or only missing evidence.", []))

    def test_missing_amount_makes_the_root_a_gap_and_routes_to_review(self) -> None:
        brief = specific_brief(amount_usd=None, missing=["amount"])
        tree = hale_tree(brief, status="ready_with_gaps")
        by_id = {node.id: node for node in tree.nodes()}
        self.assertEqual(by_id["goal"].outcome, "gap")
        self.assertEqual(by_id["cash"].outcome, "skipped")
        self.assertEqual(by_id["liquid"].outcome, "skipped")
        chosen, reason, path = route(tree)
        self.assertEqual(chosen, "review")
        self.assertIn("three questions", reason)
        self.assertEqual(path, ["goal"])

    def test_thin_liquid_cover_on_a_short_horizon(self) -> None:
        tree = hale_tree(specific_brief(amount_usd=9_000_000, horizon_months=24))
        by_id = {node.id: node for node in tree.nodes()}
        self.assertEqual((by_id["liquid"].outcome, by_id["liquid"].severity), ("misaligned", "medium"))
        self.assertEqual((by_id["horizon"].outcome, by_id["horizon"].severity), ("misaligned", "low"))
        self.assertEqual(route(tree)[2], ["goal", "cash"])

    def test_home_and_notes_nodes_appear_only_when_asked_for(self) -> None:
        brief = specific_brief(purpose="home", slices=["quotes", "home", "comps"], decisions=["Bought VNQ for income."])
        tree = hale_tree(brief)
        by_id = {node.id: node for node in tree.nodes()}
        self.assertEqual(by_id["home"].outcome, "gap")
        self.assertEqual(by_id["notes"].outcome, "pending")
        self.assertEqual(by_id["notes"].evidence_ids, ["note:1"])
        self.assertNotIn("purpose", by_id)


class PipelineTests(unittest.TestCase):
    def run_hale(self, root: Path, fake: FakeClient, notes: bool = False):
        fill(root, notes=notes)
        converse(root, SPECIFIC, fake, task_models())
        return analyze_run(root, fake, task_models())

    def test_specific_goal_runs_analyst_then_advisor(self) -> None:
        brief = specific_brief(decisions=["Bought VNQ for income."])
        fake = FakeClient(
            [
                intake_reply(amount=5_000_000, horizon=36, purpose="company", decisions=["Bought VNQ for income."]),
                analyst_reply(hale_tree(brief)),
                advisor_reply(),
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_hale(root, fake, notes=True)
            decision = json.loads((root / "decision.json").read_text())
            alert = json.loads((root / "alert.json").read_text())
            trace = json.loads((root / "pipeline.json").read_text())
            self.assertTrue((root / "brief.json").exists())
            validate_run(root)
        self.assertEqual(fake.tasks(), ["intake", "analyst", "advisor"])
        self.assertEqual([call["task"] for call in trace["calls"]], ["analyst", "advisor"])
        self.assertFalse(trace["stopped"])
        self.assertEqual(alert["route"], "urgent")
        self.assertEqual(alert["path"], ["goal", "cash"])
        self.assertEqual(alert["headline"], "James needs reachable cash the book does not hold")
        self.assertEqual(len(alert["next_actions"]), 2)
        self.assertEqual(alert["agenda"][0], "Read the goal back.")
        nodes = {node["id"]: node for node in flatten(decision["root"])}
        self.assertEqual(nodes["cash"]["finding"], "Finding for cash.")
        self.assertEqual(nodes["liquid"]["finding"], "Finding for liquid.")
        self.assertEqual((nodes["notes"]["outcome"], nodes["notes"]["severity"]), ("misaligned", "low"))
        self.assertEqual(decision["score"], 45)
        self.assertEqual(decision["verdict"], "Cash is short and the book leans on real estate.")
        self.assertEqual(result.report.score, 45)
        self.assertEqual(result.report.gap_usd, 2749999.97)
        self.assertEqual([item.severity for item in result.report.discrepancies], ["high", "medium"])

    def test_each_agent_reads_only_its_own_material(self) -> None:
        brief = specific_brief(decisions=["Bought VNQ for income."])
        fake = FakeClient(
            [
                intake_reply(amount=5_000_000, horizon=36, purpose="company", decisions=["Bought VNQ for income."]),
                analyst_reply(hale_tree(brief)),
                advisor_reply(),
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            self.run_hale(Path(tmp), fake, notes=True)
        intake_body, analyst_body, advisor_body = (user_text(call) for call in fake.calls)
        self.assertIn(SPECIFIC, intake_body)
        self.assertIn("FENWICK-NOTE-BODY", intake_body)
        self.assertNotIn("629.28", intake_body)
        self.assertNotIn("48000000", intake_body)
        self.assertNotIn("a&g eirl", intake_body)
        self.assertIn("629.28", analyst_body)
        self.assertIn("note:1", analyst_body)
        self.assertIn("Bought VNQ for income.", analyst_body)
        self.assertIn('"outcome": "misaligned"', analyst_body)
        self.assertNotIn(SPECIFIC, analyst_body)
        self.assertNotIn("FENWICK-NOTE-BODY", analyst_body)
        self.assertNotIn("live_price", analyst_body)
        self.assertNotIn("omitted:home", analyst_body)
        self.assertIn("Finding for cash.", advisor_body)
        self.assertIn('"route": "urgent"', advisor_body)
        self.assertNotIn("629.28", advisor_body)
        self.assertNotIn("live_price", advisor_body)
        self.assertNotIn("finance.yahoo.com", advisor_body)
        self.assertNotIn(SPECIFIC, advisor_body)
        self.assertEqual([call["model"] for call in fake.calls], [DEFAULT_MODEL] * 3)
        self.assertEqual([call["effort"] for call in fake.calls], ["high"] * 3)

    def test_aligned_goal_skips_the_advisor(self) -> None:
        brief = specific_brief(amount_usd=1_000, must_be_reachable=False, exclusions=[])
        fake = FakeClient(
            [
                intake_reply(amount=1_000, horizon=36, purpose="company", reachable=False, exclusions=[]),
                analyst_reply(hale_tree(brief)),
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self.run_hale(root, fake)
            alert = json.loads((root / "alert.json").read_text())
        self.assertEqual(fake.tasks(), ["intake", "analyst"])
        self.assertEqual(alert["route"], "none")
        self.assertIsNone(alert["headline"])
        self.assertEqual(result.tree.score, 100)
        self.assertEqual(result.report.discrepancies, [])

    def test_bad_citation_is_retried_once_at_the_same_effort(self) -> None:
        tree = hale_tree(specific_brief())
        fake = FakeClient(
            [
                intake_reply(amount=5_000_000, horizon=36, purpose="company"),
                analyst_reply(tree, bad_id="yahoo:NOT-A-TICKER"),
                analyst_reply(tree),
                advisor_reply(),
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_hale(root, fake)
            self.assertTrue((root / "alignment.json").exists())
        analyst_calls = [call for call in fake.calls if call["task"] == "analyst"]
        self.assertEqual(len(analyst_calls), 2)
        self.assertEqual([call["effort"] for call in analyst_calls], ["high", "high"])
        self.assertIn("unknown evidence ids", user_text(analyst_calls[1]))

    def test_missing_finding_is_rejected(self) -> None:
        tree = hale_tree(specific_brief())
        fake = FakeClient(
            [
                intake_reply(amount=5_000_000, horizon=36, purpose="company"),
                analyst_reply(tree, skip="concentration"),
                analyst_reply(tree),
                advisor_reply(),
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            self.run_hale(Path(tmp), fake)
        analyst_calls = [call for call in fake.calls if call["task"] == "analyst"]
        self.assertIn("no finding for node concentration", user_text(analyst_calls[1]))

    def test_second_failure_stops_without_a_report(self) -> None:
        tree = hale_tree(specific_brief())
        fake = FakeClient(
            [
                intake_reply(amount=5_000_000, horizon=36, purpose="company"),
                analyst_reply(tree, url="https://example.com/invented"),
                analyst_reply(tree, url="https://example.com/still-invented"),
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with self.assertRaises(CitationError):
                self.run_hale(root, fake)
            self.assertFalse((root / "alignment.json").exists())
            self.assertFalse((root / "alert.json").exists())
            self.assertTrue((root / "decision.json").exists())
            trace = json.loads((root / "pipeline.json").read_text())
        self.assertEqual([call["task"] for call in trace["calls"]], ["analyst", "analyst"])
        self.assertTrue(trace["stopped"])
        self.assertEqual(fake.tasks(), ["intake", "analyst", "analyst"])

    def test_analyze_with_a_vague_goal_prints_the_question_and_stops(self) -> None:
        fake = FakeClient([intake_reply(purpose="company", question="How much would that take?")])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fill(root)
            out = StringIO()
            with redirect_stdout(out):
                result = execute_analyze(root, VAGUE, client=fake, tasks=task_models())
        self.assertEqual(out.getvalue().strip(), "How much would that take?")
        self.assertTrue(result.trace.stopped)
        self.assertEqual(fake.tasks(), ["intake"])

    def test_analyze_with_a_specific_goal_runs_everything(self) -> None:
        fake = FakeClient(
            [
                intake_reply(amount=5_000_000, horizon=36, purpose="company"),
                analyst_reply(hale_tree(specific_brief())),
                advisor_reply(),
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fill(root)
            out = StringIO()
            with redirect_stdout(out):
                result = execute_analyze(root, SPECIFIC, client=fake, tasks=task_models())
        self.assertEqual(out.getvalue().strip(), "score=50 route=urgent calls=3")
        self.assertEqual([call.task for call in result.trace.calls], ["intake", "analyst", "advisor"])

    def test_cli_parses_converse_and_analyze(self) -> None:
        args = build_parser().parse_args(["converse", "run", "--say", VAGUE, "--reset"])
        self.assertEqual((args.command, args.say, args.reset), ("converse", VAGUE, True))
        args = build_parser().parse_args(["analyze", "run", "--goal", SPECIFIC])
        self.assertEqual((args.command, args.goal), ("analyze", SPECIFIC))


if __name__ == "__main__":
    unittest.main()
