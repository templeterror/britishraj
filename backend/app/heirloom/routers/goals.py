from fastapi import APIRouter, Request

from app.heirloom.context.access import FamilyActorDep
from app.heirloom.db import SessionDep
from app.heirloom.envelope import ok
from app.heirloom.routers.families import family_meta
from app.heirloom.services import goals, snapshots

router = APIRouter()


@router.post("/families/{family_id}/heir-goals")
def create_goal(request: Request, actor: FamilyActorDep, session: SessionDep, body: goals.GoalInput) -> dict:
    goal = goals.create(actor, session, body)
    return ok(snapshots.heir_goal_view(goal).model_dump(mode="json"), family_meta(request, actor))


@router.patch("/families/{family_id}/heir-goals/{goal_id}")
def update_goal(
    request: Request, actor: FamilyActorDep, session: SessionDep, goal_id: str, body: goals.GoalPatch
) -> dict:
    """409 `version_conflict` when `body.version` is not the stored version (saved in another tab)."""
    goal = goals.update(actor, session, goal_id, body)
    return ok(snapshots.heir_goal_view(goal).model_dump(mode="json"), family_meta(request, actor))
