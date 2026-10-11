from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.heirloom.context.access import FamilyActorDep
from app.heirloom.db import SessionDep
from app.heirloom.envelope import ApiError, ok
from app.heirloom.models import DECISION_STATUSES
from app.heirloom.routers.families import family_meta
from app.heirloom.services import decisions, snapshots

router = APIRouter()

Note = Field(min_length=1, max_length=2000)


class VerifyDecisionRequest(BaseModel):
    approved: bool
    edited_rationale: str | None = Field(default=None, max_length=4000)
    note: str | None = Field(default=None, max_length=2000)


class NoteRequest(BaseModel):
    note: str = Note


@router.get("/families/{family_id}/decisions")
def list_decisions(request: Request, actor: FamilyActorDep, session: SessionDep, status: str | None = None) -> dict:
    """The caller's own audience view of decisions (advisor: all, parent: own, heir: approved history)."""
    if status is not None and status not in DECISION_STATUSES:
        raise ApiError(422, "validation_error", f"Invalid request: status must be one of {', '.join(DECISION_STATUSES)}")
    snapshot = snapshots.build(actor, session)
    if actor.role == "adult_heir":
        rows = snapshot.approved_decisions if status in (None, "verified") else []
    else:
        rows = [d for d in snapshot.decisions if status in (None, d.verification_status)]
    return ok([row.model_dump(mode="json") for row in rows], family_meta(request, actor))


@router.post("/families/{family_id}/decisions/{decision_id}/verify")
def verify_decision(
    request: Request, actor: FamilyActorDep, session: SessionDep, decision_id: str, body: VerifyDecisionRequest
) -> dict:
    row = decisions.verify(actor, session, decision_id, body.approved, body.edited_rationale, body.note)
    return ok(snapshots.decision_dto(session, actor.family, row).model_dump(mode="json"), family_meta(request, actor))


@router.post("/families/{family_id}/decisions/{decision_id}/annotate")
def annotate_decision(
    request: Request, actor: FamilyActorDep, session: SessionDep, decision_id: str, body: NoteRequest
) -> dict:
    row = decisions.annotate(actor, session, decision_id, body.note)
    return ok(snapshots.decision_dto(session, actor.family, row).model_dump(mode="json"), family_meta(request, actor))


@router.post("/families/{family_id}/decisions/{decision_id}/request-correction")
def request_decision_correction(
    request: Request, actor: FamilyActorDep, session: SessionDep, decision_id: str, body: NoteRequest
) -> dict:
    row = decisions.request_correction(actor, session, decision_id, body.note)
    return ok(snapshots.decision_dto(session, actor.family, row).model_dump(mode="json"), family_meta(request, actor))
