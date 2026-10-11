from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.heirloom.context.access import FamilyActorDep
from app.heirloom.db import SessionDep
from app.heirloom.envelope import ok
from app.heirloom.models import ACTION_STATUSES, ACTION_TYPES
from app.heirloom.routers.families import family_meta
from app.heirloom.services import actions, activity

router = APIRouter()

DraftText = Field(default=None, max_length=4000)


class CreateActionRequest(BaseModel):
    action_type: Literal[ACTION_TYPES]
    draft_text: str | None = DraftText


class UpdateActionRequest(BaseModel):
    status: Literal[ACTION_STATUSES]
    draft_text: str | None = DraftText
    outcome_note: str | None = Field(default=None, max_length=2000)


@router.post("/families/{family_id}/insights/{insight_id}/actions")
def create_action(
    request: Request, actor: FamilyActorDep, session: SessionDep, insight_id: str, body: CreateActionRequest
) -> dict:
    """Advisor only. A draft from the type's template unless `draft_text` is given; an `heir_intro`
    that names estate details, family records or amounts is refused with 422 `heir_unsafe_text`."""
    action = actions.create(actor, session, insight_id, body.action_type, body.draft_text)
    return ok(actions.to_dto(session, action).model_dump(mode="json"), family_meta(request, actor))


@router.patch("/families/{family_id}/actions/{action_id}")
def update_action(
    request: Request, actor: FamilyActorDep, session: SessionDep, action_id: str, body: UpdateActionRequest
) -> dict:
    """409 `invalid_transition` unless draft to approved or cancelled, or approved to completed or
    cancelled; 422 `outcome_required` when completing without an `outcome_note`."""
    action = actions.update(actor, session, action_id, body.status, body.draft_text, body.outcome_note)
    return ok(actions.to_dto(session, action).model_dump(mode="json"), family_meta(request, actor))


@router.get("/families/{family_id}/actions")
def list_actions(request: Request, actor: FamilyActorDep, session: SessionDep) -> dict:
    """Advisor only, newest first. Each row keeps the `insight_id` it was created on."""
    rows = actions.list_for_advisor(actor, session)
    return ok([row.model_dump(mode="json") for row in rows], family_meta(request, actor))


@router.get("/families/{family_id}/activity")
def get_activity(request: Request, actor: FamilyActorDep, session: SessionDep) -> dict:
    """Advisor only: the latest 50 actions, audit rows and domain events, with no payload bodies."""
    rows = activity.feed(actor, session)
    return ok([row.model_dump(mode="json") for row in rows], family_meta(request, actor))
