"""Heir goals: private to the heir, versioned so a stale tab cannot overwrite a newer save."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy import update as sql_update
from sqlalchemy.orm import Session

from app.heirloom.context.access import FamilyActor, require_role
from app.heirloom.envelope import ApiError
from app.heirloom.models import GOAL_FUNDING_SOURCES, GOAL_KINDS, HeirGoal
from app.heirloom.services import audit, events, lookup
from app.heirloom.services.graph import record_ref

GoalKind = Literal[GOAL_KINDS]
FundingSource = Literal[GOAL_FUNDING_SOURCES]
Description = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Milestone = Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)]
Amount = Annotated[int, Field(gt=0, le=1_000_000_000)]
Years = Annotated[int, Field(ge=0, le=50)]

MAX_YEARS_AHEAD = 50
_NOT_NULL = ("goal_kind", "description_private", "goal_funding_source")


class GoalInput(BaseModel):
    goal_kind: GoalKind
    description_private: Description
    amount_target: Amount | None = None
    target_year: int | None = None  # as_of_year < y <= as_of_year + 50, checked against the family
    horizon_min_years: Years | None = None
    horizon_max_years: Years | None = None
    milestone: Milestone | None = None
    goal_funding_source: FundingSource = "unknown"


class GoalPatch(BaseModel):
    """Only the fields sent are changed; `version` must equal the stored version."""

    version: int
    goal_kind: GoalKind | None = None
    description_private: Description | None = None
    amount_target: Amount | None = None
    target_year: int | None = None
    horizon_min_years: Years | None = None
    horizon_max_years: Years | None = None
    milestone: Milestone | None = None
    goal_funding_source: FundingSource | None = None


def _invalid(message: str) -> ApiError:
    return ApiError(422, "validation_error", f"Invalid request: {message}")


def _validate(actor: FamilyActor, fields: dict) -> None:
    """Checks that need the family or more than one field. `fields` is the goal as it would be saved."""
    year = fields.get("target_year")
    as_of = actor.family.as_of_year
    if year is not None and not as_of < year <= as_of + MAX_YEARS_AHEAD:
        raise _invalid(f"target_year must be after {as_of} and no later than {as_of + MAX_YEARS_AHEAD}")
    low, high = fields.get("horizon_min_years"), fields.get("horizon_max_years")
    if low is not None and high is not None and low > high:
        raise _invalid("horizon_min_years must not exceed horizon_max_years")
    if fields.get("milestone") == "":
        fields["milestone"] = None  # a cleared milestone is "none", not an empty string


def _record(actor: FamilyActor, session: Session, goal: HeirGoal, action: str, event: str) -> None:
    ref = record_ref(goal)
    audit.record(session, actor.ctx.external_user_id, actor.family.id, action, "heir_goal", ref, True, "allowed")
    # No goal content in the event: the log is read by advisor-side pipelines.
    events.emit(session, actor.family, event, ref, {"goal_ref": ref, "version": goal.version})


def create(actor: FamilyActor, session: Session, data: GoalInput) -> HeirGoal:
    require_role(actor, "adult_heir")
    fields = data.model_dump()
    _validate(actor, fields)
    goal = HeirGoal(
        organization_id=actor.family.organization_id,
        family_id=actor.family.id,
        heir_person_id=actor.person.id,
        version=1,
        **fields,
    )
    session.add(goal)
    session.flush()
    _record(actor, session, goal, "heir_goal.create", "heir_goal.created.v1")
    return goal


def update(actor: FamilyActor, session: Session, goal_id: str, data: GoalPatch) -> HeirGoal:
    """Owner only. Compare-and-swap on `version`, so of two saves from the same version one gets 409."""
    require_role(actor, "adult_heir")
    goal = lookup.family_record(session, actor, HeirGoal, goal_id)
    if goal.heir_person_id != actor.person.id:
        raise ApiError(404, "not_found", "Record not found.")

    conflict = ApiError(409, "version_conflict", "This goal was updated in another window. Reload to see it.")
    if data.version != goal.version:
        raise conflict

    changes = {name: getattr(data, name) for name in data.model_fields_set - {"version"}}
    for name in _NOT_NULL:
        if name in changes and changes[name] is None:
            raise _invalid(f"{name} cannot be empty")
    current = {name: getattr(goal, name) for name in GoalInput.model_fields}
    merged = {**current, **changes}
    _validate(actor, merged)
    changes = {name: merged[name] for name in changes}

    result = session.execute(
        sql_update(HeirGoal)
        .where(HeirGoal.id == goal.id, HeirGoal.version == data.version)
        .values(**changes, version=data.version + 1)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        raise conflict  # another request saved in between the read above and this write
    session.refresh(goal)
    _record(actor, session, goal, "heir_goal.update", "heir_goal.updated.v1")
    return goal
