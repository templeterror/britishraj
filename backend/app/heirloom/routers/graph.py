from datetime import date

from fastapi import APIRouter, Request

from app.heirloom.context.access import FamilyActorDep
from app.heirloom.db import SessionDep
from app.heirloom.envelope import ok
from app.heirloom.routers.families import family_meta
from app.heirloom.services import evidence, projection

router = APIRouter()


@router.get("/families/{family_id}/graph")
def family_graph(
    request: Request, actor: FamilyActorDep, session: SessionDep, as_of: date | None = None
) -> dict:
    graph = projection.authorized_graph_projection(actor, session, as_of)
    return ok(graph.model_dump(mode="json"), family_meta(request, actor))


@router.get("/families/{family_id}/evidence/{record_ref}")
def family_evidence(request: Request, actor: FamilyActorDep, session: SessionDep, record_ref: str) -> dict:
    """404 `not_found` for refs the caller may not see, exactly as for refs that do not exist."""
    dto = evidence.get(actor, session, record_ref)
    return ok(dto.model_dump(mode="json"), family_meta(request, actor))
