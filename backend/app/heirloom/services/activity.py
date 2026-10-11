"""The advisor's activity log: actions, audit rows and domain events, newest first.

Rows say what happened to which record, never what it said: no draft text, outcome note or event
payload. What the heir does in private (editing a goal, asking the memory) is left out, so the log
cannot reveal an unshared goal.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.heirloom.context.access import FamilyActor, require_role
from app.heirloom.dto.advisor import ActivityRowDTO
from app.heirloom.models import AdvisorAction, AuditLog, DomainEvent, FamilyPerson

MAX_ROWS = 50
HEIR_PRIVATE_AUDIT = ("heir_goal.create", "heir_goal.update", "memory.ask")
HEIR_PRIVATE_EVENTS = ("heir_goal.created.v1", "heir_goal.updated.v1")


def feed(actor: FamilyActor, session: Session) -> list[ActivityRowDTO]:
    require_role(actor, "advisor")
    family = actor.family
    people = session.scalars(select(FamilyPerson).where(FamilyPerson.family_id == family.id)).all()
    by_user = {p.external_user_id: p.display_name for p in people if p.external_user_id}

    actions = session.execute(
        select(AdvisorAction, FamilyPerson.display_name)
        .join(FamilyPerson, FamilyPerson.id == AdvisorAction.advisor_person_id)
        .where(AdvisorAction.family_id == family.id)
        .order_by(AdvisorAction.updated_at.desc())
        .limit(MAX_ROWS)
    )
    # Denials from another organization's callers are logged under their own organization, not this one.
    audits = session.scalars(
        select(AuditLog)
        .where(
            AuditLog.family_id == family.id,
            AuditLog.organization_id == family.organization_id,
            AuditLog.action.not_in(HEIR_PRIVATE_AUDIT),
        )
        .order_by(AuditLog.at.desc())
        .limit(MAX_ROWS)
    )
    domain_events = session.scalars(
        select(DomainEvent)
        .where(DomainEvent.family_id == family.id, DomainEvent.type.not_in(HEIR_PRIVATE_EVENTS))
        .order_by(DomainEvent.created_at.desc())
        .limit(MAX_ROWS)
    )

    rows = [
        ActivityRowDTO(
            id=str(a.id),
            kind="action",
            at=a.updated_at,
            type=a.action_type,
            resource=f"action-{a.id}",
            actor=advisor,
            outcome=a.status,
            allowed=None,
        )
        for a, advisor in actions
    ]
    rows += [
        ActivityRowDTO(
            id=str(a.id),
            kind="audit",
            at=a.at,
            type=a.action,
            resource=a.resource_id,
            actor=by_user.get(a.actor_external_id),
            outcome=a.reason_code,
            allowed=a.allowed,
        )
        for a in audits
    ]
    rows += [
        ActivityRowDTO(
            id=str(e.id),
            kind="event",
            at=e.created_at,
            type=e.type,
            resource=e.aggregate_id,
            actor=None,
            outcome=None,
            allowed=None,
        )
        for e in domain_events
    ]
    rows.sort(key=lambda row: (row.at, row.id), reverse=True)
    return rows[:MAX_ROWS]
