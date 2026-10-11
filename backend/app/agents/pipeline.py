"""Orchestration over a run directory.

converse() runs one intake turn and saves conversation.json. analyze_run()
needs a settled conversation, builds the tree in code, has the analyst
explain it, routes it, and has the advisor write the alert when the
route is review or urgent. Every function here is a thin file wrapper
around pure functions, so an API can call the same core later.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.agents.advisor import write_alert
from app.agents.analyst import analyze, to_report
from app.agents.catalog import TaskModels
from app.agents.checks import build_tree
from app.agents.client import ChatClient, open_xai
from app.agents.intake import intake_turn
from app.agents.schemas import (
    AdvisorAlert,
    CallRecord,
    Conversation,
    DecisionTree,
    GoalBrief,
    Message,
    PipelineTrace,
)
from app.market.schemas import AlignmentReport, LiquidityFacts, MarketEvidence

CONVERSATION = "conversation.json"
REPORT_FILES = ("brief.json", "decision.json", "alignment.json", "alert.json")


@dataclass
class PipelineResult:
    trace: PipelineTrace
    conversation: Conversation
    tree: DecisionTree | None = None
    report: AlignmentReport | None = None
    alert: AdvisorAlert | None = None


def converse(
    run_directory: Path,
    text: str,
    client: ChatClient,
    tasks: TaskModels,
    reset: bool = False,
) -> tuple[Conversation, CallRecord | None]:
    conversation = Conversation() if reset else load_conversation(run_directory)
    if conversation.status != "asking":
        conversation = Conversation()
    heard = text.strip()
    if not heard:
        return conversation, None
    conversation = conversation.model_copy(
        update={"messages": [*conversation.messages, Message(role="heir", text=heard)]}
    )
    conversation, call = intake_turn(client, tasks, conversation, notes(run_directory))
    _write(run_directory / CONVERSATION, conversation)
    return conversation, call


def analyze_run(
    run_directory: Path,
    client: ChatClient,
    tasks: TaskModels,
    prior_calls: list[CallRecord] | None = None,
) -> PipelineResult:
    conversation = load_conversation(run_directory)
    calls = list(prior_calls or [])
    if conversation.status == "asking" or conversation.brief is None:
        reason = "The intake agent is still asking." if conversation.messages else "No goal was written."
        trace = PipelineTrace(stopped=True, reason=reason, calls=calls)
        _write(run_directory / "pipeline.json", trace)
        _clear(run_directory, REPORT_FILES)
        return PipelineResult(trace=trace, conversation=conversation)

    brief: GoalBrief = conversation.brief
    evidence = _read_model(run_directory / "evidence.json", MarketEvidence)
    facts = _read_model(run_directory / "facts.json", LiquidityFacts)
    tree = build_tree(brief, conversation.status, facts, evidence)
    _write(run_directory / "brief.json", brief)
    try:
        tree = analyze(client, tasks, brief, facts, evidence, tree, calls)
        alert = write_alert(client, tasks, tree, calls)
    except Exception:
        _write(run_directory / "decision.json", tree)
        _write(run_directory / "pipeline.json", PipelineTrace(stopped=True, reason="A model reply was rejected.", calls=calls))
        _clear(run_directory, ("alignment.json", "alert.json"))
        raise
    report = to_report(tree, brief, facts, evidence)
    trace = PipelineTrace(stopped=False, calls=calls)
    _write(run_directory / "decision.json", tree)
    _write(run_directory / "alignment.json", report)
    _write(run_directory / "alert.json", alert)
    _write(run_directory / "pipeline.json", trace)
    return PipelineResult(trace=trace, conversation=conversation, tree=tree, report=report, alert=alert)


def execute_converse(
    run_directory: Path,
    text: str,
    reset: bool = False,
    client: ChatClient | None = None,
    tasks: TaskModels | None = None,
) -> Conversation:
    if client is None or tasks is None:
        client, tasks = open_xai()
    conversation, _ = converse(run_directory, text, client, tasks, reset=reset)
    print(describe(conversation))
    return conversation


def execute_analyze(
    run_directory: Path,
    goal: str | None = None,
    client: ChatClient | None = None,
    tasks: TaskModels | None = None,
) -> PipelineResult:
    if client is None or tasks is None:
        client, tasks = open_xai()
    calls: list[CallRecord] = []
    if goal is not None:
        conversation, call = converse(run_directory, goal, client, tasks)
        if call is not None:
            calls.append(call)
        if conversation.status == "asking":
            print(describe(conversation))
            return PipelineResult(
                trace=PipelineTrace(stopped=True, reason="The intake agent is still asking.", calls=calls),
                conversation=conversation,
            )
    result = analyze_run(run_directory, client, tasks, calls)
    if result.trace.stopped:
        print(f"stop reason={result.trace.reason} calls={len(result.trace.calls)}")
    else:
        assert result.tree is not None and result.alert is not None
        print(f"score={result.tree.score} route={result.alert.route} calls={len(result.trace.calls)}")
    return result


def describe(conversation: Conversation) -> str:
    if conversation.status == "asking":
        agent_lines = [message.text for message in conversation.messages if message.role == "agent"]
        return agent_lines[-1] if agent_lines else "asking"
    if conversation.status == "ready_with_gaps" and conversation.brief is not None:
        return "ready with gaps: " + ", ".join(conversation.brief.missing)
    return "ready"


def load_conversation(run_directory: Path) -> Conversation:
    path = run_directory / CONVERSATION
    if not path.exists():
        return Conversation()
    return Conversation.model_validate_json(path.read_text())


def notes(run_directory: Path) -> str:
    path = run_directory / "notes.txt"
    if not path.exists():
        return ""
    return path.read_text().strip()


def _read_model(path: Path, model):
    if not path.exists():
        raise SystemExit(f"missing {path.name}")
    return model.model_validate_json(path.read_text())


def _clear(run_directory: Path, names: tuple[str, ...]) -> None:
    for name in names:
        path = run_directory / name
        if path.exists():
            path.unlink()


def _write(path: Path, model) -> None:
    path.write_text(model.model_dump_json(indent=2) + "\n")
