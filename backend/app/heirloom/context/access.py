"""Family-scoped authorisation. The actor's role comes from the database, never from the request."""

from dataclasses import dataclass
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, object_session

from app.heirloom.context.auth_context import ContextDep, RequestContext
from app.heirloom.db import SessionDep
from app.heirloom.envelope import ApiError
from app.heirloom.models import Family, FamilyPerson
from app.heirloom.services import audit

Role = Literal["advisor", "parent", "adult_heir"]
ROLES = ("advisor", "parent", "adult_heir")


@dataclass
class FamilyActor:
    ctx: RequestContext
    family: Family
    person: FamilyPerson
    role: Role


def _deny(
    session: Session, ctx: RequestContext, family_id: UUID, action: str, error: ApiError, reason: str
) -> ApiError:
    audit.record(
        session,
        ctx.external_user_id,
        family_id,
        action,
        "family",
        str(family_id),
        False,
        reason,
        organization_id=ctx.organization_id,
    )
    session.commit()  # the request is about to fail, and the request-scoped session rolls back on error
    return error


def require_family(family_id: UUID, ctx: RequestContext, session: Session) -> FamilyActor:
    """The caller's membership in `family_id`, or 404 (never 403: other orgs' families do not exist)."""
    not_found = ApiError(404, "family_not_found", "Family not found.")
    family = session.get(Family, family_id)
    if family is None or family.organization_id != ctx.organization_id:
        raise _deny(session, ctx, family_id, "family.access", not_found, "not_member")
    person = session.scalars(
        select(FamilyPerson).where(
            FamilyPerson.family_id == family_id,
            FamilyPerson.organization_id == ctx.organization_id,
            FamilyPerson.external_user_id == ctx.external_user_id,
        )
    ).first()
    if person is None or person.family_role not in ROLES:
        raise _deny(session, ctx, family_id, "family.access", not_found, "not_member")
    return FamilyActor(ctx=ctx, family=family, person=person, role=cast(Role, person.family_role))


def require_role(actor: FamilyActor, *roles: Role) -> FamilyActor:
    if actor.role in roles:
        return actor
    session = object_session(actor.family)  # the session `require_family` loaded the family in
    raise _deny(
        session,
        actor.ctx,
        actor.family.id,
        "family.role_check",
        ApiError(403, "forbidden_for_role", "This action is not available for your role."),
        "role_not_permitted",
    )


def family_actor(family_id: UUID, ctx: ContextDep, session: SessionDep) -> FamilyActor:
    return require_family(family_id, ctx, session)


FamilyActorDep = Annotated[FamilyActor, Depends(family_actor)]
