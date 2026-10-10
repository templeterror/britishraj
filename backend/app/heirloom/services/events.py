"""Domain events: an append-only log whose length is the family's `data_revision`."""

import uuid
from collections import defaultdict
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.heirloom.models import DomainEvent, Family

Handler = Callable[[Session, Family, DomainEvent], None]

_handlers: dict[str, list[Handler]] = defaultdict(list)


def register(type_or_star: str, handler: Handler) -> None:
    """Run `handler` synchronously for events of this type, or for every event with `"*"`.

    Registering the same handler twice is a no-op, so each `create_app` can register its handlers.
    """
    if handler not in _handlers[type_or_star]:
        _handlers[type_or_star].append(handler)


def clear_handlers() -> None:
    _handlers.clear()


def emit(
    session: Session,
    family: Family,
    type: str,
    aggregate_ref: str,
    payload: dict,
    idempotency_key: str | None = None,
) -> bool:
    """Record an event and bump `family.data_revision`; False when `idempotency_key` was already used."""
    key = idempotency_key or f"{type}:{uuid.uuid4()}"
    if session.scalar(select(DomainEvent.id).where(DomainEvent.idempotency_key == key)) is not None:
        return False
    event = DomainEvent(
        organization_id=family.organization_id,
        family_id=family.id,
        type=type,
        aggregate_id=aggregate_ref,
        event_payload=payload,
        idempotency_key=key,
    )
    session.add(event)
    family.data_revision = Family.data_revision + 1  # SQL-side increment: safe under concurrent writers
    session.flush()
    session.refresh(family)
    for handler in (*_handlers.get(type, ()), *_handlers.get("*", ())):
        handler(session, family, event)
    return True
