from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.heirloom.context.access import FamilyActorDep
from app.heirloom.db import SessionDep
from app.heirloom.envelope import ok
from app.heirloom.routers.families import family_meta
from app.heirloom.services import insights

router = APIRouter()


class ReviewRequest(BaseModel):
    review_status: insights.ReviewStatus


@router.get("/families/{family_id}/insights")
def list_insights(
    request: Request,
    actor: FamilyActorDep,
    session: SessionDep,
    status: str | None = None,
    tag: str | None = None,
) -> dict:
    """Advisor only. Never includes `invalidated` insights or ones whose heir goal is no longer shared."""
    rows = insights.list_for_advisor(actor, session, status, tag)
    return ok([row.model_dump(mode="json") for row in rows], family_meta(request, actor))


@router.post("/families/{family_id}/insights/{insight_id}/review")
def review_insight(
    request: Request, actor: FamilyActorDep, session: SessionDep, insight_id: str, body: ReviewRequest
) -> dict:
    dto = insights.set_review(actor, session, insight_id, body.review_status)
    return ok(dto.model_dump(mode="json"), family_meta(request, actor))


@router.get("/families/{family_id}/forecasts/{scenario_id}")
def get_forecast(request: Request, actor: FamilyActorDep, session: SessionDep, scenario_id: str) -> dict:
    """Advisor only; 404 `not_found` for unknown ids and for forecasts of a goal no longer shared."""
    dto = insights.forecast_for_advisor(actor, session, scenario_id)
    return ok(dto.model_dump(mode="json"), family_meta(request, actor))
