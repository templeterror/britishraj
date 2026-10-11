from typing import Annotated

from fastapi import APIRouter, Request
from pydantic import BaseModel, StringConstraints

from app.heirloom.context.access import FamilyActorDep
from app.heirloom.db import SessionDep
from app.heirloom.envelope import ok
from app.heirloom.routers.families import family_meta
from app.heirloom.services import memory_qa

router = APIRouter()


class AskRequest(BaseModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


@router.post("/families/{family_id}/memory/ask")
def ask(request: Request, actor: FamilyActorDep, session: SessionDep, body: AskRequest) -> dict:
    answer = memory_qa.ask(actor, session, body.question)
    return ok(answer.model_dump(mode="json"), family_meta(request, actor))
