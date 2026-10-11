"""Consent grants, and the advisor's view of heir goals that those grants allow.

`goal_view_for_advisor` is the single gate every advisor-facing read (snapshot, graph projection,
evidence, readiness) goes through to see an heir goal. Callers use it as
`consent.goal_view_for_advisor(...)` so its body can change without touching them.

Grants default off. A change bumps `family.consent_revision` and emits `consent.changed.v1`, whose
handler withdraws every goal-derived insight computed under an older revision.

Who may set what: an adult heir shares their own goals with the family advisor (heir-only, always);
a parent shares their own verified decisions with an adult heir; and the family advisor may record a
parent's sharing instruction for a verified decision, citing the conversation it came from. The
parent stays the grantor of an advisor-recorded grant; the advisor is only `recorded_by`.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.heirloom.context.access import FamilyActor
from app.heirloom.dto.advisor import AdvisorGoalDetail, AdvisorGoalSummary
from app.heirloom.dto.common import ConsentGrantDTO, ConsentState
from app.heirloom.envelope import ApiError
from app.heirloom.models import (
    AdvisorAction,
    ConsentGrant,
    DecisionRecord,
    DomainEvent,
    Family,
    FamilyPerson,
    HeirGoal,
    Insight,
    SourceDocument,
)
from app.heirloom.services import audit, events
from app.heirloom.services.graph import record_ref

GOAL_SCOPES = ("goal_summary", "goal_detail")
NOT_IN_PILOT = ("estate_intent", "balances")
UNSENT_ACTION_STATUSES = ("draft", "approved")
CONSENT_CHANGED = "consent.changed.v1"
CONVERSATION_SOURCE_TYPES = ("transcript", "meeting_note")
EARLIEST_BASIS_DATE = date(2000, 1, 1)
ADVISOR_RECORDED_REASON = "advisor_recorded_client_instruction"


# --- Advisor goal view -------------------------------------------------------------------------


def _amount_band(amount: int | None) -> tuple[str, int | None]:
    """`(label, mid)`: the amount rounded half-up to the nearest $100K, e.g. `("about $500K", 500000)`."""
    if amount is None:
        return "amount not set", None
    mid = (amount + 50_000) // 100_000 * 100_000
    if mid == 0:
        return "under $50K", 50_000
    if mid >= 1_000_000:
        return f"about ${mid / 1_000_000:g}M", mid
    return f"about ${mid // 1000}K", mid


def _horizon_band(goal: HeirGoal) -> str:
    low, high = goal.horizon_min_years, goal.horizon_max_years
    if low is not None and high is not None:
        return f"{low} years" if low == high else f"{low}–{high} years"
    if goal.target_year is not None:
        return f"by {goal.target_year}"
    if high is not None:
        return f"within {high} years"
    if low is not None:
        return f"{low}+ years"
    return "timing not set"


def _active_goal_scopes(session: Session, family: Family, goal: HeirGoal) -> set[str]:
    """Scopes the goal's own heir actively granted to an advisor of this family."""
    advisors = select(FamilyPerson.id).where(
        FamilyPerson.family_id == family.id, FamilyPerson.family_role == "advisor"
    )
    return set(
        session.scalars(
            select(ConsentGrant.share_scope).where(
                ConsentGrant.family_id == family.id,
                ConsentGrant.resource_type == "heir_goal",
                ConsentGrant.resource_id == goal.id,
                ConsentGrant.grantor_person_id == goal.heir_person_id,
                ConsentGrant.recipient_person_id.in_(advisors),
                ConsentGrant.share_scope.in_(GOAL_SCOPES),
                ConsentGrant.active.is_(True),
            )
        )
    )


def goal_view_for_advisor(
    session: Session, family: Family, goal: HeirGoal
) -> AdvisorGoalSummary | AdvisorGoalDetail | None:
    """What the family advisor may see of `goal`, or None when the heir has not shared it.

    Detail always rides on a summary grant (revoking the summary revokes detail), so a detail grant
    without an active summary shows nothing.
    """
    if goal.family_id != family.id:
        return None
    scopes = _active_goal_scopes(session, family, goal)
    if "goal_summary" not in scopes:
        return None
    amount_band, amount_mid = _amount_band(goal.amount_target)
    summary = {
        "goal_id": str(goal.id),
        "kind": goal.goal_kind,
        "horizon_band": _horizon_band(goal),
        "amount_band": amount_band,
        "amount_band_mid": amount_mid,
        "horizon_max_years": goal.horizon_max_years,
    }
    if "goal_detail" not in scopes:
        return AdvisorGoalSummary(**summary)
    return AdvisorGoalDetail(
        **summary,
        amount_target=goal.amount_target,
        target_year=goal.target_year,
        milestone=goal.milestone,
        description=goal.description_private,
    )


# --- Granting ----------------------------------------------------------------------------------


class GrantBasis(BaseModel):
    """The conversation a sharing instruction came from. Required when the advisor records one."""

    conversation_date: date
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    # A family transcript or meeting note, by its `external_ref` (e.g. `meeting-2026-04-15`).
    source_ref: Annotated[str, StringConstraints(strip_whitespace=True, max_length=128)] | None = None


@dataclass(frozen=True)
class _Target:
    """What a permitted request changes: whose grant on which resource, and how it is recorded."""

    resource_type: str
    resource: HeirGoal | DecisionRecord
    grantor_id: UUID
    recorded_via: str  # "self" | "advisor_recorded"


@dataclass(frozen=True)
class _Provenance:
    recorded_by: str
    recorded_via: str
    basis_date: date | None = None
    basis_note: str | None = None
    basis_source_id: UUID | None = None


def _deny(
    actor: FamilyActor, session: Session, resource_id: UUID, scope: str, error: ApiError, reason: str
) -> ApiError:
    audit.record(
        session,
        actor.ctx.external_user_id,
        actor.family.id,
        "consent.set",
        "consent",
        f"{scope}:{resource_id}",
        False,
        reason,
    )
    session.commit()  # keep the denial: the request-scoped session rolls back on error
    return error


def _forbidden(actor: FamilyActor, session: Session, resource_id: UUID, scope: str) -> ApiError:
    error = ApiError(403, "consent_not_permitted", "You cannot share this record with that person.")
    return _deny(actor, session, resource_id, scope, error, "consent_not_permitted")


def _family_row(session: Session, family: Family, model, row_id: UUID):
    row = session.get(model, row_id)
    return row if row is not None and row.family_id == family.id else None


def _resolve(
    actor: FamilyActor, session: Session, resource_id: UUID, scope: str, recipient_id: UUID
) -> _Target | None:
    """The grant this actor may set for `scope` on the resource toward `recipient_id`, else None."""
    family, me = actor.family, actor.person
    recipient = _family_row(session, family, FamilyPerson, recipient_id)
    if recipient is None:
        return None
    if scope in GOAL_SCOPES:
        goal = _family_row(session, family, HeirGoal, resource_id)
        if (
            actor.role == "adult_heir"
            and goal is not None
            and goal.heir_person_id == me.id
            and recipient.family_role == "advisor"
        ):
            return _Target("heir_goal", goal, me.id, "self")
    elif scope == "decision_excerpt":
        decision = _family_row(session, family, DecisionRecord, resource_id)
        if (
            decision is None
            or decision.verification_status != "verified"
            or recipient.family_role != "adult_heir"
        ):
            return None
        if actor.role == "parent" and decision.person_id == me.id:
            return _Target("decision", decision, me.id, "self")
        if actor.role == "advisor":
            owner = _family_row(session, family, FamilyPerson, decision.person_id)
            if owner is not None and owner.family_role == "parent":
                return _Target("decision", decision, owner.id, "advisor_recorded")
    return None


def _basis_source(session: Session, family: Family, basis: GrantBasis) -> SourceDocument | None:
    """Validate `basis`; the cited conversation record, if any. Raises 422 on a bad date or source."""
    if not EARLIEST_BASIS_DATE <= basis.conversation_date <= datetime.now(UTC).date():
        raise ApiError(
            422, "invalid_basis_date", "The conversation date must be between 2000-01-01 and today."
        )
    if not basis.source_ref:
        return None
    source = session.scalars(
        select(SourceDocument).where(
            SourceDocument.family_id == family.id,
            SourceDocument.external_ref == basis.source_ref,
            SourceDocument.source_type.in_(CONVERSATION_SOURCE_TYPES),
        )
    ).first()
    if source is None:
        raise ApiError(422, "unknown_source", "Cite a transcript or meeting note from this family.")
    return source


def _grant_row(
    session: Session, actor: FamilyActor, target: _Target, scope: str, recipient_id: UUID
) -> ConsentGrant:
    grant = session.scalars(
        select(ConsentGrant).where(
            ConsentGrant.family_id == actor.family.id,
            ConsentGrant.grantor_person_id == target.grantor_id,
            ConsentGrant.recipient_person_id == recipient_id,
            ConsentGrant.resource_type == target.resource_type,
            ConsentGrant.resource_id == target.resource.id,
            ConsentGrant.share_scope == scope,
        )
    ).first()
    if grant is None:
        grant = ConsentGrant(
            organization_id=actor.family.organization_id,
            family_id=actor.family.id,
            grantor_person_id=target.grantor_id,
            recipient_person_id=recipient_id,
            resource_type=target.resource_type,
            resource_id=target.resource.id,
            share_scope=scope,
            active=False,
            revision=actor.family.consent_revision,
            recorded_by=actor.ctx.external_user_id,
            recorded_via=target.recorded_via,
        )
        session.add(grant)
    return grant


def _apply(grant: ConsentGrant, active: bool, provenance: _Provenance, now: datetime) -> bool:
    """Set the grant's state and the provenance of this change; True when that changed it."""
    if grant.active == active:
        return False
    grant.active = active
    grant.recorded_by = provenance.recorded_by
    grant.recorded_via = provenance.recorded_via
    grant.basis_date = provenance.basis_date
    grant.basis_note = provenance.basis_note
    grant.basis_source_id = provenance.basis_source_id
    if active:
        grant.effective_at, grant.revoked_at = now, None
    else:
        grant.revoked_at = now
    return True


def grant_dto(grant: ConsentGrant) -> ConsentGrantDTO:
    return ConsentGrantDTO(
        id=str(grant.id),
        resource_type=grant.resource_type,
        resource_id=str(grant.resource_id),
        scope=grant.share_scope,
        recipient_person_id=str(grant.recipient_person_id),
        active=grant.active,
        effective_at=grant.effective_at,
        revoked_at=grant.revoked_at,
        revision=grant.revision,
    )


def set_grant(
    actor: FamilyActor,
    session: Session,
    resource_id: UUID,
    scope: str,
    recipient_person_id: UUID,
    active: bool,
    basis: GrantBasis | None = None,
) -> ConsentState:
    """Switch one grant on or off. `goal_detail` on also turns `goal_summary` on; `goal_summary` off
    also turns `goal_detail` off. Estate intent and balances are never shareable in the pilot.

    The advisor can never set an heir's goal consent (403 `forbidden_for_role`). When the advisor
    records a parent's decision sharing, `basis` is required both to share and to stop sharing.
    A supplied basis is validated and stored with the change whoever makes it.
    """
    if scope in NOT_IN_PILOT:
        raise ApiError(422, "not_available_in_pilot", "Sharing this is not available in this pilot.")
    if actor.role == "advisor" and scope in GOAL_SCOPES:
        error = ApiError(403, "forbidden_for_role", "Only the heir can share their own goals.")
        raise _deny(actor, session, resource_id, scope, error, "role_not_permitted")
    target = _resolve(actor, session, resource_id, scope, recipient_person_id)
    if target is None:
        raise _forbidden(actor, session, resource_id, scope)
    advisor_recorded = target.recorded_via == "advisor_recorded"
    if advisor_recorded and basis is None:
        raise ApiError(422, "basis_required", "Record the conversation this instruction came from.")
    source = _basis_source(session, actor.family, basis) if basis is not None else None
    provenance = _Provenance(
        recorded_by=actor.ctx.external_user_id,
        recorded_via=target.recorded_via,
        basis_date=basis.conversation_date if basis else None,
        basis_note=basis.note if basis else None,
        basis_source_id=source.id if source else None,
    )

    def row(s: str) -> ConsentGrant:
        return _grant_row(session, actor, target, s, recipient_person_id)

    now = datetime.now(UTC)
    grant = row(scope)
    changed = [grant] if _apply(grant, active, provenance, now) else []
    linked = {("goal_detail", True): "goal_summary", ("goal_summary", False): "goal_detail"}.get((scope, active))
    if linked is not None:
        other = row(linked)
        if _apply(other, active, provenance, now):
            changed.append(other)

    family = actor.family
    ref = record_ref(target.resource)
    if changed:
        family.consent_revision = Family.consent_revision + 1  # SQL-side increment, like data_revision
        session.flush()
        session.refresh(family)
        for g in changed:
            g.revision = family.consent_revision
        if advisor_recorded:
            reason = ADVISOR_RECORDED_REASON
        else:
            reason = "granted" if active else "revoked"
        audit.record(
            session, actor.ctx.external_user_id, family.id, "consent.set", "consent", f"{scope}:{ref}", True, reason
        )
        events.emit(
            session,
            family,
            CONSENT_CHANGED,
            ref,
            {
                "resource_type": target.resource_type,
                "resource_ref": ref,
                "scopes": sorted(g.share_scope for g in changed),
                "active": active,
                "recorded_via": target.recorded_via,
                "consent_revision": family.consent_revision,
            },
        )
    session.flush()
    return ConsentState(grant=grant_dto(grant), consent_revision=family.consent_revision)


# --- Revocation chain --------------------------------------------------------------------------


def on_consent_changed(session: Session, family: Family, _event: DomainEvent) -> None:
    """Withdraw goal-derived insights computed under an older consent revision, and their unsent drafts."""
    stale = [
        insight
        for insight in session.scalars(
            select(Insight).where(
                Insight.family_id == family.id,
                Insight.consent_revision < family.consent_revision,
                Insight.review_status != "invalidated",
            )
        )
        if (insight.payload or {}).get("goal_ref")
    ]
    if not stale:
        return
    for insight in stale:
        insight.review_status = "invalidated"
        insight.payload = {"withdrawn": "consent_revoked"}
    for action in session.scalars(
        select(AdvisorAction).where(
            AdvisorAction.insight_id.in_([i.id for i in stale]),
            AdvisorAction.status.in_(UNSENT_ACTION_STATUSES),
        )
    ):
        action.status = "cancelled"
        action.draft_text = ""
    session.flush()


def register_handlers() -> None:
    """Idempotent (`events.register` ignores duplicates)."""
    events.register(CONSENT_CHANGED, on_consent_changed)
