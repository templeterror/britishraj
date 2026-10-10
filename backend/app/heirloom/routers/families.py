from fastapi import APIRouter, Request
from sqlalchemy import select

from app.heirloom.context.access import FamilyActorDep
from app.heirloom.context.auth_context import ContextDep
from app.heirloom.db import SessionDep
from app.heirloom.envelope import Meta, ok
from app.heirloom.models import Family, FamilyPerson

router = APIRouter()


@router.get("/families/{family_id}/revision")
def revision(request: Request, actor: FamilyActorDep) -> dict:
    family = actor.family
    meta = Meta(
        revision=family.data_revision,
        consent_revision=family.consent_revision,
        mode=request.app.state.settings.mode,
    )
    return ok({"revision": family.data_revision, "consent_revision": family.consent_revision}, meta)


@router.get("/me/families")
def my_families(request: Request, ctx: ContextDep, session: SessionDep) -> dict:
    rows = session.execute(
        select(Family, FamilyPerson)
        .join(FamilyPerson, FamilyPerson.family_id == Family.id)
        .where(
            FamilyPerson.external_user_id == ctx.external_user_id,
            Family.organization_id == ctx.organization_id,
            FamilyPerson.family_role.in_(("advisor", "parent", "adult_heir")),
        )
        .order_by(Family.display_name)
    ).all()
    data = [
        {
            "family_id": str(family.id),
            "display_name": family.display_name,
            "role": person.family_role,
            "person_id": str(person.id),
        }
        for family, person in rows
    ]
    return ok(data, Meta(mode=request.app.state.settings.mode))
