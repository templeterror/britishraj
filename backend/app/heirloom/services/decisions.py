"""Decision-record verification: a candidate becomes history only after the advisor verifies it."""

from sqlalchemy.orm import Session

from app.heirloom.context.access import FamilyActor, require_role
from app.heirloom.envelope import ApiError
from app.heirloom.models import DecisionRecord
from app.heirloom.services import audit, events, lookup
from app.heirloom.services.graph import record_ref


def _clean(text: str | None) -> str | None:
    return (text or "").strip() or None


def _audit(actor: FamilyActor, session: Session, action: str, ref: str, reason: str) -> None:
    audit.record(session, actor.ctx.external_user_id, actor.family.id, action, "decision", ref, True, reason)


def verify(
    actor: FamilyActor,
    session: Session,
    decision_id: str,
    approved: bool,
    edited_rationale: str | None,
    note: str | None,
) -> DecisionRecord:
    """Advisor-only; a decision leaves `candidate` exactly once, to `verified` or `rejected`."""
    require_role(actor, "advisor")
    decision = lookup.family_record(session, actor, DecisionRecord, decision_id)
    if decision.verification_status != "candidate":
        raise ApiError(
            409, "invalid_transition", f"A {decision.verification_status} decision cannot be verified again."
        )
    note = _clean(note)
    if not approved and note is None:
        raise ApiError(422, "note_required", "Add a note explaining why this decision is rejected.")

    ref = record_ref(decision)
    if approved:
        edited = _clean(edited_rationale)
        if edited is not None and edited != decision.rationale_text:
            decision.rationale_text = edited
            decision.rationale_edited = True
        decision.verification_status = "verified"
        decision.verified_by = actor.person.id
    else:
        decision.verification_status = "rejected"
    if note is not None:
        decision.advisor_note = note

    _audit(actor, session, "decision.verify", ref, decision.verification_status)
    events.emit(
        session,
        actor.family,
        "decision.verified.v1",
        ref,
        {"decision_ref": ref, "status": decision.verification_status, "rationale_edited": decision.rationale_edited},
    )
    return decision


def annotate(actor: FamilyActor, session: Session, decision_id: str, note: str) -> DecisionRecord:
    require_role(actor, "advisor")
    decision = lookup.family_record(session, actor, DecisionRecord, decision_id)
    decision.advisor_note = _clean(note)
    ref = record_ref(decision)
    _audit(actor, session, "decision.annotate", ref, "allowed")
    events.emit(session, actor.family, "decision.annotated.v1", ref, {"decision_ref": ref})
    return decision


def request_correction(actor: FamilyActor, session: Session, decision_id: str, note: str) -> DecisionRecord:
    """A parent flags their own decision as misrecorded; the advisor sees the note and re-reviews."""
    require_role(actor, "parent")
    decision = lookup.family_record(session, actor, DecisionRecord, decision_id)
    if decision.person_id != actor.person.id:
        raise ApiError(404, "not_found", "Record not found.")
    decision.advisor_note = _clean(note)
    ref = record_ref(decision)
    _audit(actor, session, "decision.request_correction", ref, "allowed")
    events.emit(session, actor.family, "decision.correction_requested.v1", ref, {"decision_ref": ref})
    return decision
