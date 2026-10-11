from uuid import UUID

from sqlalchemy.orm import Session

from app.heirloom.models import AuditLog, Family


def record(
    session: Session,
    actor_external_id: str,
    family_id: UUID | None,
    action: str,
    resource_type: str,
    resource_id: str | None,
    allowed: bool,
    reason_code: str,
    *,
    organization_id: str | None = None,
) -> None:
    """Add an audit row (flushed, not committed).

    `organization_id` is the caller's org. It defaults to the family's org, which is only right when
    the actor was already authorised for that family, so denials pass it explicitly.
    """
    if organization_id is None:
        family = session.get(Family, family_id) if family_id else None
        organization_id = family.organization_id if family else "unknown"
    session.add(
        AuditLog(
            organization_id=organization_id,
            actor_external_id=actor_external_id,
            family_id=family_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            allowed=allowed,
            reason_code=reason_code,
        )
    )
    session.flush()
