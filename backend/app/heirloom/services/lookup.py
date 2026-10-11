"""Resolve a route's record id (a UUID or a business ref) to a row of the caller's own family."""

from uuid import UUID

from sqlalchemy.orm import Session

from app.heirloom.context.access import FamilyActor
from app.heirloom.envelope import ApiError
from app.heirloom.services import graph as graph_service


def family_record(session: Session, actor: FamilyActor, model, ident: str):
    """The family's `model` row named by `ident`; 404 `not_found` for unknown ids and other families' rows."""
    row = None
    try:
        row = session.get(model, UUID(ident))
    except ValueError:
        pass
    if row is None or row.family_id != actor.family.id:
        row = graph_service.find_record(session, actor.family, ident, (model,))
    if row is None:
        raise ApiError(404, "not_found", "Record not found.")
    return row
