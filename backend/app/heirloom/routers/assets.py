from fastapi import APIRouter, Request

from app.heirloom.context.access import FamilyActorDep
from app.heirloom.db import SessionDep
from app.heirloom.envelope import ok
from app.heirloom.routers.families import family_meta
from app.heirloom.services import asset_terms, snapshots

router = APIRouter()


@router.patch("/families/{family_id}/assets/{asset_id}/terms")
def update_terms(
    request: Request, actor: FamilyActorDep, session: SessionDep, asset_id: str, body: asset_terms.TermsPatch
) -> dict:
    """Advisor only. `liquidatable_fraction: null` records the term as unknown (attorney review)."""
    asset = asset_terms.update(actor, session, asset_id, body)
    return ok(snapshots.asset_dto(asset).model_dump(mode="json"), family_meta(request, actor))
