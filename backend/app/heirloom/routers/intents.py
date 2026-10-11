from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.heirloom.context.access import FamilyActorDep
from app.heirloom.db import SessionDep
from app.heirloom.envelope import ok
from app.heirloom.routers.families import family_meta
from app.heirloom.services import intents, snapshots

router = APIRouter()


class ImportRequest(BaseModel):
    fixture_ref: intents.FixtureRef


class VerifyIntentRequest(BaseModel):
    verified: bool
    notes: str | None = Field(default=None, max_length=2000)
    source_version: int


class InstrumentStatusRequest(BaseModel):
    status: Literal["superseded"]


@router.post("/families/{family_id}/estate-intents/import")
def import_intents(request: Request, actor: FamilyActorDep, session: SessionDep, body: ImportRequest) -> dict:
    rows = intents.import_fixture(actor, session, body.fixture_ref)
    data = [snapshots.intent_dto(session, actor.family, row).model_dump(mode="json") for row in rows]
    return ok(data, family_meta(request, actor))


@router.post("/families/{family_id}/estate-intents/{intent_id}/verify")
def verify_intent(
    request: Request, actor: FamilyActorDep, session: SessionDep, intent_id: str, body: VerifyIntentRequest
) -> dict:
    row = intents.verify(actor, session, intent_id, body.verified, body.notes, body.source_version)
    return ok(snapshots.intent_dto(session, actor.family, row).model_dump(mode="json"), family_meta(request, actor))


@router.post("/families/{family_id}/estate-intents/{intent_id}/counsel-reviewed")
def counsel_reviewed(request: Request, actor: FamilyActorDep, session: SessionDep, intent_id: str) -> dict:
    row = intents.mark_counsel_reviewed(actor, session, intent_id)
    return ok(snapshots.intent_dto(session, actor.family, row).model_dump(mode="json"), family_meta(request, actor))


@router.post("/families/{family_id}/instruments/{instrument_id}/status")
def instrument_status(
    request: Request, actor: FamilyActorDep, session: SessionDep, instrument_id: str, body: InstrumentStatusRequest
) -> dict:
    row = intents.set_instrument_status(actor, session, instrument_id, body.status)
    data = snapshots.instrument_dto(session, actor.family, row).model_dump(mode="json")
    return ok(data, family_meta(request, actor))
