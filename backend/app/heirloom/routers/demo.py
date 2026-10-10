from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.heirloom.context.auth_context import ContextDep, issue_demo_token
from app.heirloom.db import SessionDep
from app.heirloom.envelope import ApiError, Meta, ok
from app.heirloom.models import FamilyPerson
from app.heirloom.services.seed import reset_and_seed

PERSONAS = {
    "sarah": "demo_sarah",
    "robert": "demo_robert",
    "james": "demo_james",
    "other_advisor": "demo_other_advisor",
}


class SessionRequest(BaseModel):
    persona: Literal["sarah", "robert", "james", "other_advisor"]


def _demo_only(request: Request) -> None:
    if request.app.state.settings.mode != "demo":
        raise ApiError(404, "not_found", "Not found.")


# Router-level, so clerk mode answers 404 before any authentication is attempted.
router = APIRouter(prefix="/demo", dependencies=[Depends(_demo_only)])


@router.post("/sessions")
def create_session(body: SessionRequest, request: Request, session: SessionDep) -> dict:
    settings = request.app.state.settings
    person = session.scalars(
        select(FamilyPerson).where(FamilyPerson.external_user_id == PERSONAS[body.persona])
    ).first()
    if person is None:
        raise ApiError(404, "not_found", "Demo persona is not seeded.")
    token = issue_demo_token(person.external_user_id, person.organization_id, settings)
    data = {
        "token": token,
        "family_id": str(person.family_id),
        "person": {"id": str(person.id), "display_name": person.display_name, "role": person.family_role},
    }
    return ok(data, Meta(mode=settings.mode))


@router.post("/reset")
def reset(request: Request, _ctx: ContextDep, session: SessionDep) -> dict:
    reset_and_seed(session)
    return ok({"reset": True}, Meta(mode=request.app.state.settings.mode))
