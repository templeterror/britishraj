"""One model reads the words. Code decides whether a report is needed. Another model writes it."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.agents.analyze import analyze
from app.agents.catalog import TaskModels
from app.agents.client import ChatClient, open_gateway
from app.agents.schemas import Alert, PipelineTrace, TriageDecision
from app.agents.triage import decide, read_brief
from app.market.schemas import AlignmentReport, LiquidityFacts, MarketEvidence

SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3}


@dataclass
class PipelineResult:
    triage: TriageDecision
    trace: PipelineTrace
    report: AlignmentReport | None = None
    alert: Alert | None = None


def analyze_run(
    run_directory: Path,
    goal: str,
    client: ChatClient,
    tasks: TaskModels,
) -> PipelineResult:
    if not goal.strip():
        decision = TriageDecision(
            stop=True,
            reason="No goal was written.",
            slices=[],
            clarity="clear",
        )
        trace = PipelineTrace(stopped=True, calls=[])
        _write(run_directory / "triage.json", decision)
        _write(run_directory / "pipeline.json", trace)
        _clear_report(run_directory)
        return PipelineResult(triage=decision, trace=trace)

    evidence = _read_model(run_directory / "evidence.json", MarketEvidence)
    facts = _read_model(run_directory / "facts.json", LiquidityFacts)
    notes = _notes(run_directory)
    brief, intake_call = read_brief(client, tasks, goal.strip(), notes)
    calls = [intake_call]
    decision = decide(brief, facts)
    if decision.stop:
        trace = PipelineTrace(stopped=True, calls=calls)
        _write(run_directory / "triage.json", decision)
        _write(run_directory / "pipeline.json", trace)
        _clear_report(run_directory)
        return PipelineResult(triage=decision, trace=trace)

    try:
        report = analyze(client, tasks, brief, facts, evidence, decision.slices, calls)
    except Exception:
        _write(run_directory / "triage.json", decision)
        _write(run_directory / "pipeline.json", PipelineTrace(stopped=True, calls=calls))
        _clear_report(run_directory)
        raise
    alert = build_alert(report)
    trace = PipelineTrace(stopped=False, calls=calls)
    _write(run_directory / "triage.json", decision)
    _write(run_directory / "alignment.json", report)
    _write(run_directory / "alert.json", alert)
    _write(run_directory / "pipeline.json", trace)
    return PipelineResult(triage=decision, trace=trace, report=report, alert=alert)


def build_alert(report: AlignmentReport) -> Alert:
    if not report.discrepancies:
        return Alert(
            severity="low",
            claim=report.verdict,
            verdict=report.verdict,
            agenda=list(report.meeting_agenda),
        )
    best = report.discrepancies[0]
    for item in report.discrepancies[1:]:
        if SEVERITY_RANK[item.severity] > SEVERITY_RANK[best.severity]:
            best = item
    return Alert(
        severity=best.severity,
        claim=best.claim,
        verdict=report.verdict,
        agenda=list(report.meeting_agenda),
    )


def execute_analyze(
    run_directory: Path,
    goal: str | None,
    client: ChatClient | None = None,
    tasks: TaskModels | None = None,
) -> PipelineResult:
    if client is None or tasks is None:
        client, tasks = open_gateway()
    text = goal if goal is not None else _goal_file(run_directory)
    result = analyze_run(run_directory, text, client, tasks)
    if result.trace.stopped:
        print(f"stop reason={result.triage.reason} calls={len(result.trace.calls)}")
    else:
        assert result.report is not None and result.alert is not None
        print(
            f"score={result.report.score} severity={result.alert.severity} "
            f"calls={len(result.trace.calls)}"
        )
    return result


def _goal_file(run_directory: Path) -> str:
    path = run_directory / "goal.txt"
    if not path.exists():
        return ""
    return path.read_text()


def _notes(run_directory: Path) -> str:
    path = run_directory / "notes.txt"
    if not path.exists():
        return ""
    return path.read_text().strip()


def _read_model(path: Path, model):
    if not path.exists():
        raise SystemExit(f"missing {path.name}")
    return model.model_validate_json(path.read_text())


def _clear_report(run_directory: Path) -> None:
    for name in ("alignment.json", "alert.json"):
        path = run_directory / name
        if path.exists():
            path.unlink()


def _write(path: Path, model) -> None:
    path.write_text(model.model_dump_json(indent=2) + "\n")
