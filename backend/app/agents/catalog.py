"""Pick a model and a high thinking effort from the live gateway catalog.

Defaults were read from GET /v1/models on 2026-10-10.

The language pass uses Grok 4.7. The report uses GPT-5.5.
Both accept structured JSON and effort "high".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from pydantic import BaseModel


DEFAULT_INTAKE_MODEL = "spacexai/grok-4.7"
DEFAULT_ANALYST_MODEL = "openai/gpt-5.5"
HIGH_EFFORT = "high"


class ModelSpec(BaseModel):
    id: str
    efforts: tuple[str, ...]
    structured: bool


@dataclass(frozen=True)
class TaskModels:
    intake_model: str
    intake_effort: str
    analyst_model: str
    analyst_effort: str


def model_spec(row: dict) -> ModelSpec:
    efforts: list[str] = []
    for option in row.get("reasoning_options") or []:
        if option.get("type") == "effort":
            efforts.extend(str(value) for value in option.get("values") or [])
    tags = set(row.get("tags") or [])
    params = set(row.get("supported_parameters") or [])
    structured = (
        "structured-output" in tags
        or "structured_outputs" in params
        or "response_format" in params
    )
    return ModelSpec(id=row["id"], efforts=tuple(efforts), structured=structured)


def specs_by_id(catalog: list[dict]) -> dict[str, ModelSpec]:
    return {spec.id: spec for spec in (model_spec(row) for row in catalog)}


def resolve_tasks(catalog: list[dict], env: Mapping[str, str] | None = None) -> TaskModels:
    env = env or {}
    specs = specs_by_id(catalog)
    intake_id = env.get("AGENT_TRIAGE_MODEL") or DEFAULT_INTAKE_MODEL
    analyst_id = env.get("AGENT_ANALYST_MODEL") or DEFAULT_ANALYST_MODEL
    intake = _require(specs, intake_id)
    analyst = _require(specs, analyst_id)
    if not intake.structured:
        raise ValueError(f"{intake_id} cannot return JSON")
    if not analyst.structured:
        raise ValueError(f"{analyst_id} cannot return JSON")
    _require_effort(intake, HIGH_EFFORT)
    _require_effort(analyst, HIGH_EFFORT)
    return TaskModels(
        intake_model=intake.id,
        intake_effort=HIGH_EFFORT,
        analyst_model=analyst.id,
        analyst_effort=HIGH_EFFORT,
    )


def effort_allowed(spec: ModelSpec, effort: str) -> None:
    if effort not in spec.efforts:
        allowed = ", ".join(spec.efforts) or "none"
        raise ValueError(f"{spec.id} does not allow effort {effort} ({allowed})")


def _require(specs: dict[str, ModelSpec], model_id: str) -> ModelSpec:
    spec = specs.get(model_id)
    if spec is None:
        raise ValueError(f"{model_id} is not in the model catalog")
    return spec


def _require_effort(spec: ModelSpec, effort: str) -> None:
    if effort not in spec.efforts:
        raise ValueError(f"{spec.id} has no {effort} effort")
