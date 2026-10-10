from fastapi import APIRouter, Request
from sqlalchemy import select

from app.heirloom.context.access import FamilyActor, FamilyActorDep
from app.heirloom.context.auth_context import ContextDep
from app.heirloom.db import SessionDep
from app.heirloom.envelope import Meta, ok
from app.heirloom.graph.factory import get_graph_repo
from app.heirloom.models import Family, FamilyPerson
from app.heirloom.services import snapshots

router = APIRouter()


def family_meta(request: Request, actor: FamilyActor) -> Meta:
    """Envelope meta for a family-scoped response, including degraded features (e.g. the graph store)."""
    _repo, degraded = get_graph_repo()
    return Meta(
        revision=actor.family.data_revision,
        consent_revision=actor.family.consent_revision,
        mode=request.app.state.settings.mode,
        degraded=degraded,
    )


@router.get("/families/{family_id}/revision")
def revision(request: Request, actor: FamilyActorDep) -> dict:
    family = actor.family
    meta = Meta(
        revision=family.data_revision,
        consent_revision=family.consent_revision,
        mode=request.app.state.settings.mode,
    )
    return ok({"revision": family.data_revision, "consent_revision": family.consent_revision}, meta)


@router.get("/families/{family_id}/snapshot")
def snapshot(request: Request, actor: FamilyActorDep, session: SessionDep) -> dict:
    """The caller's own audience DTO; the audience is the caller's family role, never a parameter."""
    data = snapshots.build(actor, session)
    return ok(data.model_dump(mode="json"), family_meta(request, actor))


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
