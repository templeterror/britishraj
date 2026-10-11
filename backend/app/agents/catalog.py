"""Which xAI model each agent uses, and the thinking effort it runs at.

Every agent runs on Grok 4.7 at effort "high" unless an AGENT_*_MODEL
variable names another model from KNOWN_MODELS. The table was read from
docs.x.ai on 2026-10-10. Add a row when xAI ships a model you want to use.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

DEFAULT_MODEL = "grok-4.7"
HIGH_EFFORT = "high"

KNOWN_MODELS: dict[str, tuple[str, ...]] = {
    "grok-4.7": ("low", "medium", "high", "xhigh"),
    "grok-4.6": ("low", "medium", "high", "xhigh"),
    "grok-4.5": ("low", "medium", "high"),
}


@dataclass(frozen=True)
class TaskModels:
    intake_model: str
    intake_effort: str
    analyst_model: str
    analyst_effort: str
    advisor_model: str
    advisor_effort: str


def resolve_tasks(env: Mapping[str, str] | None = None) -> TaskModels:
    env = env or {}
    intake = env.get("AGENT_INTAKE_MODEL") or DEFAULT_MODEL
    analyst = env.get("AGENT_ANALYST_MODEL") or DEFAULT_MODEL
    advisor = env.get("AGENT_ADVISOR_MODEL") or analyst
    for model in (intake, analyst, advisor):
        effort_allowed(model, HIGH_EFFORT)
    return TaskModels(
        intake_model=intake,
        intake_effort=HIGH_EFFORT,
        analyst_model=analyst,
        analyst_effort=HIGH_EFFORT,
        advisor_model=advisor,
        advisor_effort=HIGH_EFFORT,
    )


def effort_allowed(model: str, effort: str) -> None:
    efforts = KNOWN_MODELS.get(model)
    if efforts is None:
        known = ", ".join(KNOWN_MODELS)
        raise ValueError(f"{model} is not a known xAI model ({known})")
    if effort not in efforts:
        raise ValueError(f"{model} does not allow effort {effort} ({', '.join(efforts)})")
