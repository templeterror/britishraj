"""Read the heir's words once. Prices and evidence stay with the analyst."""

from __future__ import annotations

import json

from app.agents.catalog import TaskModels
from app.agents.client import ChatClient, Completion, json_schema
from app.agents.schemas import CallRecord, IntakeBrief, TriageDecision
from app.market.schemas import LiquidityFacts

INTAKE_INSTRUCTIONS = (
    "Read the heir's goal and any meeting notes. You do not have prices, accounts, or market pages. "
    "Extract the dollar amount they need to reach, the horizon, and a one-sentence intent. "
    "Choose slices only from what those words ask for: "
    "quotes when they need money they can reach, home for a residence, "
    "comps for nearby sales, funding for a company or a raise. "
    "decisions are investment choices stated in the notes, and stay empty when there are no notes. "
    "ambiguous is true when the amount or the aim is unclear. "
    "Leave amount_usd empty when they name no amount."
)


def read_brief(
    client: ChatClient,
    tasks: TaskModels,
    goal: str,
    notes: str,
) -> tuple[IntakeBrief, CallRecord]:
    payload: dict = {"goal": goal}
    if notes:
        payload["notes"] = notes
    messages = [
        {"role": "system", "content": INTAKE_INSTRUCTIONS},
        {"role": "user", "content": json.dumps(payload)},
    ]
    completion = client.complete(
        task="intake",
        model=tasks.intake_model,
        effort=tasks.intake_effort,
        messages=messages,
        schema_name="intake_brief",
        schema=json_schema(IntakeBrief),
    )
    return IntakeBrief.model_validate_json(completion.text), record("intake", completion)


def decide(brief: IntakeBrief, facts: LiquidityFacts) -> TriageDecision:
    clarity = "ambiguous" if brief.ambiguous else "clear"
    if brief.amount_usd is None or brief.amount_usd <= 0:
        return TriageDecision(
            stop=True,
            reason="The goal names no amount of money.",
            slices=[],
            clarity=clarity,
        )
    if facts.cash_reachable >= brief.amount_usd:
        return TriageDecision(
            stop=True,
            reason="Cash already covers the need.",
            slices=[],
            clarity=clarity,
        )
    slices = list(dict.fromkeys(brief.slices)) or ["quotes"]
    return TriageDecision(stop=False, reason=brief.intent, slices=slices, clarity=clarity)


def record(task: str, completion: Completion) -> CallRecord:
    return CallRecord(
        task=task,
        model=completion.model,
        effort=completion.effort,
        prompt_tokens=completion.prompt_tokens,
        completion_tokens=completion.completion_tokens,
        total_tokens=completion.total_tokens,
    )
