"""The intake agent reads the heir's words and asks until the goal is specific.

The model extracts a brief from the whole transcript each turn and phrases
one question. Code decides whether that question is needed: amount and
horizon are required, purpose is nice to have, and the agent may ask at
most MAX_QUESTIONS times before the pipeline proceeds with the gaps on record.
The model never sees prices or accounts.
"""

from __future__ import annotations

import json

from app.agents.catalog import TaskModels
from app.agents.client import ChatClient, Completion, json_schema
from app.agents.schemas import (
    CallRecord,
    Conversation,
    GoalBrief,
    IntakeTurn,
    Message,
    Missing,
    SliceName,
)

MAX_QUESTIONS = 3
REQUIRED: tuple[Missing, ...] = ("amount", "horizon")

INTAKE_INSTRUCTIONS = (
    "You help an heir describe a financial goal in their own words. "
    "You have no prices, accounts, or market pages, so never state or suggest a number. "
    "Read the whole transcript and any meeting notes, then fill the brief as far as the words allow: "
    "intent is one sentence stating the aim; amount_usd is the dollar figure they need, "
    "amount_is_estimate true when they said about, roughly, or a range (use the midpoint); "
    "horizon_months is when they need it, converted to months; "
    "purpose is company for a business or a raise, home for a residence, education, family, or other; "
    "must_be_reachable is true when they say the money has to be accessible, liquid, or usable; "
    "exclusions are kinds of money they said do not count, in their words; "
    "decisions are investment choices stated in the notes, one per entry, and stay empty without notes. "
    "List in missing each of amount, horizon, purpose that the transcript does not answer. "
    "Write one short, warm question for the single most important missing item, in this order: amount, horizon, purpose. "
    "Never ask about something the transcript already answers. "
    "Leave question empty when nothing is missing."
)


def intake_turn(
    client: ChatClient,
    tasks: TaskModels,
    conversation: Conversation,
    notes: str = "",
) -> tuple[Conversation, CallRecord]:
    payload: dict = {
        "transcript": [message.model_dump() for message in conversation.messages],
    }
    if notes:
        payload["notes"] = notes
    completion = client.complete(
        task="intake",
        model=tasks.intake_model,
        effort=tasks.intake_effort,
        messages=[
            {"role": "system", "content": INTAKE_INSTRUCTIONS},
            {"role": "user", "content": json.dumps(payload)},
        ],
        schema_name="intake_turn",
        schema=json_schema(IntakeTurn),
    )
    turn = IntakeTurn.model_validate_json(completion.text)
    brief = settle(turn.brief)
    return advance(conversation, brief, turn.question), record("intake", completion)


def settle(brief: GoalBrief) -> GoalBrief:
    """Code owns the derived fields: what is missing and which evidence slices apply."""
    missing: list[Missing] = []
    if brief.amount_usd is None or brief.amount_usd <= 0:
        missing.append("amount")
    if brief.horizon_months is None or brief.horizon_months <= 0:
        missing.append("horizon")
    if brief.purpose is None:
        missing.append("purpose")
    return brief.model_copy(update={"missing": missing, "slices": slices_for(brief.purpose)})


def slices_for(purpose: str | None) -> list[SliceName]:
    slices: list[SliceName] = ["quotes"]
    if purpose == "home":
        slices.extend(["home", "comps"])
    if purpose == "company":
        slices.append("funding")
    return slices


def advance(conversation: Conversation, brief: GoalBrief, question: str | None) -> Conversation:
    required_missing = [item for item in brief.missing if item in REQUIRED]
    budget_left = conversation.questions_asked < MAX_QUESTIONS
    if not brief.missing or (not required_missing and not budget_left):
        return conversation.model_copy(update={"brief": brief, "status": "ready"})
    if not budget_left:
        return conversation.model_copy(update={"brief": brief, "status": "ready_with_gaps"})
    text = (question or "").strip() or fallback_question(brief.missing[0])
    return conversation.model_copy(
        update={
            "brief": brief,
            "status": "asking",
            "questions_asked": conversation.questions_asked + 1,
            "messages": [*conversation.messages, Message(role="agent", text=text)],
        }
    )


def fallback_question(item: Missing) -> str:
    if item == "amount":
        return "Roughly how much money would this take?"
    if item == "horizon":
        return "When would you need it by?"
    return "What is the money for?"


def record(task: str, completion: Completion) -> CallRecord:
    return CallRecord(
        task=task,
        model=completion.model,
        effort=completion.effort,
        prompt_tokens=completion.prompt_tokens,
        completion_tokens=completion.completion_tokens,
        total_tokens=completion.total_tokens,
    )
