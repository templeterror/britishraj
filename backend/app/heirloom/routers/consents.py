from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.heirloom.context.access import FamilyActorDep, require_role
from app.heirloom.db import SessionDep
from app.heirloom.dto.parent import HeirPreview
from app.heirloom.envelope import ok
from app.heirloom.models import SHARE_SCOPES, FamilyPerson
from app.heirloom.routers.families import family_meta
from app.heirloom.services import consent, snapshots

router = APIRouter()


class ConsentRequest(BaseModel):
    scope: Literal[SHARE_SCOPES]
    recipient_person_id: UUID
    active: bool


@router.put("/families/{family_id}/consents/{resource_id}")
def set_consent(
    request: Request, actor: FamilyActorDep, session: SessionDep, resource_id: UUID, body: ConsentRequest
) -> dict:
    state = consent.set_grant(actor, session, resource_id, body.scope, body.recipient_person_id, body.active)
    return ok(state.model_dump(mode="json"), family_meta(request, actor))


@router.get("/families/{family_id}/heir-preview")
def heir_preview(request: Request, actor: FamilyActorDep, session: SessionDep) -> dict:
    """Parent only: exactly the approved decisions the family's adult heir sees."""
    require_role(actor, "parent")
    heir = session.scalars(
        select(FamilyPerson)
        .where(FamilyPerson.family_id == actor.family.id, FamilyPerson.family_role == "adult_heir")
        .order_by(FamilyPerson.display_name, FamilyPerson.id)
    ).first()
    approved = snapshots.heir_approved_decisions(session, actor.family, heir) if heir else []
    return ok(HeirPreview(approved_decisions=approved).model_dump(mode="json"), family_meta(request, actor))
