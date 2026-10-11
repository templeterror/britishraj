"""The evidence drawer: the dated source behind one graph record, if this actor may see it.

Unauthorized and unknown refs get the same 404, so a ref's existence never leaks. Every read, allowed
or denied, is audited.
"""

from sqlalchemy.orm import Session

from app.heirloom.context.access import FamilyActor
from app.heirloom.dto.advisor import AdvisorGoalDetail
from app.heirloom.dto.common import EvidenceDTO
from app.heirloom.envelope import ApiError
from app.heirloom.models import (
    Asset,
    DecisionRecord,
    FamilyPerson,
    HeirGoal,
    LegalInstrument,
    SourceDocument,
    TransferIntent,
)
from app.heirloom.services import audit
from app.heirloom.services import graph as graph_service
from app.heirloom.services.projection import Visibility
from app.heirloom.services.seed import FIXTURE_DIR

_EVIDENCE_MODELS = (DecisionRecord, TransferIntent, LegalInstrument, Asset, HeirGoal)


def read_source_text(document: SourceDocument | None) -> str | None:
    """The document's text (demo mode keeps sources as fixture files); None when unavailable."""
    if document is None:
        return None
    path = (FIXTURE_DIR / document.storage_key).resolve()
    if not path.is_relative_to(FIXTURE_DIR) or not path.is_file():
        return None
    return path.read_text().strip()


def _display_name(session: Session, person_id) -> str | None:
    person = session.get(FamilyPerson, person_id) if person_id else None
    return person.display_name if person else None


def _source(session: Session, source_id) -> SourceDocument | None:
    return session.get(SourceDocument, source_id) if source_id else None


def _revocability(instrument: LegalInstrument | None) -> str:
    if instrument is None or instrument.revocable is None:
        return "Documented intent (revocability not stated); not a transfer of ownership."
    if instrument.revocable:
        return "Revocable documented intent; not a transfer of ownership."
    return "Documented intent; not a transfer of ownership."


def _decision(session: Session, ref: str, decision: DecisionRecord) -> EvidenceDTO:
    source = _source(session, decision.source_document_id)
    locator = dict(decision.source_locator or {})
    if decision.verification_status == "verified":
        qualifier = f"Verified by {_display_name(session, decision.verified_by) or 'the advisor'}"
        if decision.rationale_edited:
            qualifier += "; rationale edited by the advisor"
    else:
        qualifier = "Candidate extracted from the source; not yet verified by the advisor"
    return EvidenceDTO(
        record_ref=ref,
        title=decision.action_text,
        kind="decision",
        status=decision.verification_status,
        qualifier=qualifier,
        document_title=source.title if source else None,
        document_date=source.document_date if source else None,
        excerpt=locator.get("quoted_span") or decision.rationale_text,
        locator=locator or None,
    )


def _intent(session: Session, ref: str, intent: TransferIntent) -> EvidenceDTO:
    instrument = session.get(LegalInstrument, intent.instrument_id)
    source = _source(session, instrument.source_document_id if instrument else None)
    parts = [_revocability(instrument)]
    if intent.conditions:
        parts.append("Conditions: " + "; ".join(intent.conditions) + ".")
    if intent.status == "superseded":
        parts.append(f"Superseded{f' on {intent.valid_to.isoformat()}' if intent.valid_to else ''}.")
    elif intent.status == "contested":
        parts.append("Conflicting instruments: legal review required.")
    elif intent.status == "proposed":
        parts.append("Candidate; not yet verified by the advisor.")
    beneficiary = _display_name(session, intent.beneficiary_person_id)
    return EvidenceDTO(
        record_ref=ref,
        title=f"{intent.allocation_description}, intended for {beneficiary}",
        kind="estate_intent",
        status=intent.status,
        qualifier=" ".join(parts),
        document_title=source.title if source else None,
        document_date=source.document_date if source else None,
        excerpt=read_source_text(source),
        locator=None,
    )


def _instrument(session: Session, ref: str, instrument: LegalInstrument) -> EvidenceDTO:
    source = _source(session, instrument.source_document_id)
    return EvidenceDTO(
        record_ref=ref,
        title=instrument.title,
        kind="estate_instrument",
        status=instrument.status,
        qualifier=_revocability(instrument),
        document_title=source.title if source else None,
        document_date=source.document_date if source else instrument.effective_date,
        excerpt=read_source_text(source),
        locator=None,
    )


def _asset(session: Session, ref: str, asset: Asset) -> EvidenceDTO:
    source = _source(session, asset.data_source_id)
    qualifier = f"Synthetic {asset.liquidity_class} holding"
    if asset.as_of_date:
        qualifier += f", as of {asset.as_of_date.isoformat()}"
    if graph_service.has_restriction(asset):
        qualifier += f". {graph_service.restriction_label(asset)}."
    return EvidenceDTO(
        record_ref=ref,
        title=asset.label,
        kind="asset",
        status=asset.verified_status,
        qualifier=qualifier,
        document_title=source.title if source else None,
        document_date=source.document_date if source else None,
        excerpt=read_source_text(source),
        locator=None,
    )


def _goal(vis: Visibility, ref: str, goal: HeirGoal) -> EvidenceDTO | None:
    title = f"{goal.goal_kind.replace('_', ' ').capitalize()} goal"
    if vis.own_goal(goal):
        return EvidenceDTO(
            record_ref=ref,
            title=title,
            kind="goal",
            status="private",
            qualifier="Private to you unless you choose to share it.",
            document_title=None,
            document_date=None,
            excerpt=goal.description_private,
            locator=None,
        )
    view = vis.advisor_goal(goal)
    if view is None:
        return None
    detail = isinstance(view, AdvisorGoalDetail)
    return EvidenceDTO(
        record_ref=ref,
        title=title,
        kind="goal",
        status="shared_detail" if detail else "shared_summary",
        qualifier=f"Shared by the heir: {view.amount_band}, {view.horizon_band}",
        document_title=None,
        document_date=None,
        excerpt=view.description if detail else None,
        locator=None,
    )


def _heir_decision(vis: Visibility, ref: str, decision: DecisionRecord) -> EvidenceDTO:
    """An heir sees an approved decision exactly as their approved-history view shows it."""
    view = vis.heir_decisions[str(decision.id)]
    locator = dict(view.locator or {})
    return EvidenceDTO(
        record_ref=ref,
        title=view.title,
        kind="decision",
        status="verified",
        qualifier="Shared with you by your family",
        document_title=view.source_title,
        document_date=view.date,
        excerpt=locator.get("quoted_span") or view.rationale,
        locator=locator or None,
    )


def _build(vis: Visibility, session: Session, ref: str, row) -> EvidenceDTO | None:
    match row:
        case DecisionRecord() if vis.decision(row):
            if vis.role == "adult_heir":
                return _heir_decision(vis, ref, row)
            return _decision(session, ref, row)
        case TransferIntent() if vis.intent(row):
            return _intent(session, ref, row)
        case LegalInstrument() if vis.instrument(row):
            return _instrument(session, ref, row)
        case Asset() if vis.asset(row):
            return _asset(session, ref, row)
        case HeirGoal():
            return _goal(vis, ref, row)
    return None


def get(actor: FamilyActor, session: Session, record_ref: str) -> EvidenceDTO:
    row = graph_service.find_record(session, actor.family, record_ref, _EVIDENCE_MODELS)
    dto = None if row is None else _build(Visibility(actor, session), session, record_ref, row)
    allowed = dto is not None
    audit.record(
        session,
        actor.ctx.external_user_id,
        actor.family.id,
        "evidence.read",
        "evidence",
        record_ref[:200],
        allowed,
        "allowed" if allowed else "not_visible",
    )
    if not allowed:
        session.commit()  # keep the denial: the request-scoped session rolls back on error
        raise ApiError(404, "not_found", "Record not found.")
    return dto
