"""Advisor actions: drafts the advisor reviews, approves and records the outcome of.

Nothing here sends a message. An approved `heir_intro` shows the heir an invitation card inside
Heirloom Relay, and only after passing `heir_text_guard`. An action keeps the insight row it was
created on: a recompute replaces insight rows but never re-points actions, so clients group a flag's
actions by `insight_key`.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.heirloom.context.access import FamilyActor, require_role
from app.heirloom.dto.advisor import AdvisorActionDTO
from app.heirloom.dto.heir import InvitationView
from app.heirloom.envelope import ApiError
from app.heirloom.models import (
    AdvisorAction,
    Asset,
    Family,
    FamilyPerson,
    HeirGoal,
    Insight,
    LegalInstrument,
    utc_now,
)
from app.heirloom.services import audit, consent, events, heir_text_guard, insights
from app.heirloom.services.graph import find_record

ACTION_UPDATED = "advisor_action.updated.v1"
TRANSITIONS = {"draft": ("approved", "cancelled"), "approved": ("completed", "cancelled")}
INVITING_STATUSES = ("approved", "completed")

PARENT_REVIEW = (
    "Agenda — review with Robert (and estate counsel if he wishes)\n"
    "1. Confirm the 2026 estate planning letter still reflects Robert's intent for the LLC interest.\n"
    "2. Review the operating agreement's partner-consent and sale provisions and how they would apply "
    "after a transfer.\n"
    "3. Discuss whether Robert wants the plan to address liquidity for whoever receives the interest.\n"
    "Robert's portfolio continues to be managed for Robert's own objectives; nothing here is a "
    "recommendation to change it."
)
HEIR_INTRO = (
    "Hi James, thanks for sharing your plans to build a company. If it would help, I'd be glad to offer a "
    "no-pressure planning conversation about funding options and timing for your own goals. Best, Sarah"
)
TEMPLATES = {"parent_review": PARENT_REVIEW, "heir_intro": HEIR_INTRO}  # other types start blank


def _invalid(message: str) -> ApiError:
    return ApiError(422, "validation_error", f"Invalid request: {message}")


def _family_terms(session: Session, family: Family) -> list[str]:
    """What an heir-facing text must never name: the family's asset labels and instrument titles."""
    return [
        *session.scalars(select(Asset.label).where(Asset.family_id == family.id)),
        *session.scalars(select(LegalInstrument.title).where(LegalInstrument.family_id == family.id)),
    ]


def _provided(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        raise _invalid("draft_text cannot be blank")
    return cleaned


def _guarded(session: Session, family: Family, action_type: str, text: str) -> str:
    """`text`, after the heir-safe check that applies to an `heir_intro` (422 `heir_unsafe_text`)."""
    if action_type == "heir_intro":
        heir_text_guard.require_safe(text, _family_terms(session, family))
    return text


def _load(actor: FamilyActor, session: Session, action_id: str) -> AdvisorAction:
    try:
        action = session.get(AdvisorAction, UUID(action_id))
    except ValueError:
        action = None
    if action is None or action.family_id != actor.family.id:
        raise ApiError(404, "not_found", "Record not found.")
    return action


def _record(actor: FamilyActor, session: Session, action: AdvisorAction, insight: Insight, name: str) -> None:
    """Audit and announce a change. Neither carries the draft or the outcome note."""
    ref = f"action-{action.id}"
    audit.record(
        session, actor.ctx.external_user_id, actor.family.id, name, "advisor_action", ref, True, action.status
    )
    events.emit(
        session,
        actor.family,
        ACTION_UPDATED,
        ref,
        {
            "action_ref": ref,
            "insight_key": insight.insight_key,
            "action_type": action.action_type,
            "status": action.status,
        },
    )
    session.refresh(action)  # times read back as the database stores them, like every other DTO's


def create(
    actor: FamilyActor, session: Session, insight_id: str, action_type: str, draft_text: str | None
) -> AdvisorAction:
    """A draft action on a flag the advisor can see. `draft_text` defaults to the type's template."""
    require_role(actor, "advisor")
    insight = insights.get_visible(actor, session, insight_id)
    text = TEMPLATES.get(action_type, "") if draft_text is None else _provided(draft_text)
    action = AdvisorAction(
        organization_id=actor.family.organization_id,
        family_id=actor.family.id,
        insight_id=insight.id,
        advisor_person_id=actor.person.id,
        action_type=action_type,
        draft_text=_guarded(session, actor.family, action_type, text),
        status="draft",
    )
    session.add(action)
    session.flush()
    insight.review_status = "actioned"
    _record(actor, session, action, insight, "action.create")
    return action


def update(
    actor: FamilyActor,
    session: Session,
    action_id: str,
    status: str,
    draft_text: str | None = None,
    outcome_note: str | None = None,
) -> AdvisorAction:
    """draft to approved or cancelled, approved to completed or cancelled; anything else is 409.

    `draft_text` replaces the draft while it is still a draft. Completing needs an `outcome_note`.
    """
    require_role(actor, "advisor")
    action = _load(actor, session, action_id)
    if status not in TRANSITIONS.get(action.status, ()):
        raise ApiError(409, "invalid_transition", f"A {action.status} action cannot become {status}.")
    note = (outcome_note or "").strip() or None
    if status == "completed" and note is None:
        raise ApiError(422, "outcome_required", "Record the outcome before marking this action completed.")
    text = None
    if draft_text is not None:
        if action.status != "draft":
            raise ApiError(409, "invalid_transition", "Only a draft can be edited.")
        text = _guarded(session, actor.family, action.action_type, _provided(draft_text))

    insight = session.get(Insight, action.insight_id)
    action.status = status
    action.updated_at = utc_now()
    if text is not None:
        action.draft_text = text
    if note is not None:
        action.outcome_note = note
    if status == "approved":
        action.reviewed_by = actor.person.id
        if insight.review_status != "invalidated":  # a recompute may have replaced the row since
            insight.review_status = "actioned"
    _record(actor, session, action, insight, "action.update")
    return action


def to_dto(session: Session, action: AdvisorAction) -> AdvisorActionDTO:
    key = session.scalar(select(Insight.insight_key).where(Insight.id == action.insight_id))
    return _dto(action, key)


def _dto(action: AdvisorAction, insight_key: str) -> AdvisorActionDTO:
    return AdvisorActionDTO(
        id=str(action.id),
        insight_id=str(action.insight_id),
        insight_key=insight_key,
        action_type=action.action_type,
        status=action.status,
        draft_text=action.draft_text,
        outcome_note=action.outcome_note,
        created_at=action.created_at,
        updated_at=action.updated_at,
    )


def list_for_advisor(actor: FamilyActor, session: Session) -> list[AdvisorActionDTO]:
    """Every action of the family, newest first, each with the key of the insight it was created on."""
    require_role(actor, "advisor")
    rows = session.execute(
        select(AdvisorAction, Insight.insight_key)
        .join(Insight, Insight.id == AdvisorAction.insight_id)
        .where(AdvisorAction.family_id == actor.family.id)
        .order_by(AdvisorAction.created_at.desc(), AdvisorAction.id)
    )
    return [_dto(action, key) for action, key in rows]


def invitations_for(session: Session, family: Family, heir: FamilyPerson) -> list[InvitationView]:
    """Approved or completed `heir_intro` actions about this heir's own goal, while it is still shared.

    The single source for the heir snapshot's `invitations`. A draft is never shown, and revoking the
    goal share ends every invitation: approved ones are cancelled, completed ones lose their insight.
    """
    rows = session.execute(
        select(AdvisorAction, Insight, FamilyPerson.display_name)
        .join(Insight, Insight.id == AdvisorAction.insight_id)
        .join(FamilyPerson, FamilyPerson.id == AdvisorAction.advisor_person_id)
        .where(
            AdvisorAction.family_id == family.id,
            AdvisorAction.action_type == "heir_intro",
            AdvisorAction.status.in_(INVITING_STATUSES),
        )
        .order_by(AdvisorAction.created_at, AdvisorAction.id)
    )
    invitations = []
    for action, insight, advisor_name in rows:
        goal_ref = (insight.payload or {}).get("goal_ref")
        goal = find_record(session, family, goal_ref, (HeirGoal,)) if goal_ref else None
        if goal is None or goal.heir_person_id != heir.id:
            continue
        if consent.goal_view_for_advisor(session, family, goal) is None:
            continue
        invitations.append(
            InvitationView(from_display=advisor_name, text=action.draft_text, status=action.status)
        )
    return invitations
