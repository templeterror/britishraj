"""Estate-intent verification: documented intent is a candidate until the advisor verifies it.

Only a verified intent on a verified instrument earns an `INTENDED_FOR` edge. Current verified or
contested intents that name different beneficiaries for one asset contest each other and none earns the edge;
once only one beneficiary is left among them, the contested intents are verified again.
"""

import hashlib
from datetime import UTC, date, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.heirloom.context.access import FamilyActor, require_role
from app.heirloom.envelope import ApiError
from app.heirloom.ids import ref_id
from app.heirloom.models import (
    Asset,
    FamilyPerson,
    LegalInstrument,
    SourceDocument,
    TransferIntent,
)
from app.heirloom.services import audit, events, lookup
from app.heirloom.services.graph import record_ref
from app.heirloom.services.seed import FIXTURE_DIR

FixtureRef = Literal["conflicting_amendment"]

# The deterministic "extractor": what reading each fixture document yields. No model is called.
_FIXTURES = {
    "conflicting_amendment": {
        "file": "conflicting_amendment.txt",
        "source": {"ref": "source-amendment-2026", "title": "Amendment to letter of intent, 2026-09-01"},
        "document_date": date(2026, 9, 1),
        "instrument": {
            "ref": "instr-amendment-2026",
            "title": "First amendment to letter of intent, 2026",
            "instrument_type": "letter_of_intent",
            "revocable": True,
        },
        "beneficiary": {"ref": "person-claire", "display_name": "Claire Morgan", "family_role": "other"},
        "intent": {
            "ref": "intent-claire-llc",
            "asset": "asset-family-llc",
            "allocation_description": "Robert's 40% membership interest",
            "conditions": ["Revocable; may be amended by Robert at any time", "Not yet reviewed by estate counsel"],
            "confidence": 0.88,
        },
    }
}


def _now() -> datetime:
    return datetime.now(UTC)


def _find(session: Session, actor: FamilyActor, model, ref: str):
    row = session.get(model, ref_id(ref))
    return row if row is not None and row.family_id == actor.family.id else None


def import_fixture(actor: FamilyActor, session: Session, fixture_ref: FixtureRef) -> list[TransferIntent]:
    """Create the fixture's reported instrument and proposed intent(s). Importing twice changes nothing."""
    require_role(actor, "advisor")
    spec = _FIXTURES[fixture_ref]
    family = actor.family
    scope = {"organization_id": family.organization_id, "family_id": family.id}

    asset = _find(session, actor, Asset, spec["intent"]["asset"])
    if asset is None:
        raise ApiError(422, "fixture_not_applicable", "This fixture does not apply to this family.")

    existing = _find(session, actor, TransferIntent, spec["intent"]["ref"])
    if existing is not None:
        return [existing]

    text = (FIXTURE_DIR / spec["file"]).read_bytes()
    source = SourceDocument(
        id=ref_id(spec["source"]["ref"]),
        external_ref=spec["source"]["ref"],
        source_type="estate_instrument",
        title=spec["source"]["title"],
        storage_key=spec["file"],
        document_date=spec["document_date"],
        checksum=hashlib.sha256(text).hexdigest(),
        uploaded_by=actor.ctx.external_user_id,
        **scope,
    )
    person = spec["beneficiary"]
    beneficiary = _find(session, actor, FamilyPerson, person["ref"]) or FamilyPerson(
        id=ref_id(person["ref"]),
        external_ref=person["ref"],
        display_name=person["display_name"],
        family_role=person["family_role"],
        **scope,
    )
    session.add_all([source, beneficiary])
    session.flush()

    ins = spec["instrument"]
    instrument = LegalInstrument(
        id=ref_id(ins["ref"]),
        external_ref=ins["ref"],
        instrument_type=ins["instrument_type"],
        title=ins["title"],
        effective_date=spec["document_date"],
        revocable=ins["revocable"],
        status="reported",
        source_document_id=source.id,
        **scope,
    )
    session.add(instrument)
    session.flush()

    t = spec["intent"]
    intent = TransferIntent(
        id=ref_id(t["ref"]),
        external_ref=t["ref"],
        instrument_id=instrument.id,
        asset_id=asset.id,
        beneficiary_person_id=beneficiary.id,
        allocation_description=t["allocation_description"],
        conditions=list(t["conditions"]),
        advisor_verified=False,
        confidence=t["confidence"],
        status="proposed",
        valid_from=spec["document_date"],
        **scope,
    )
    session.add(intent)
    session.flush()

    ref = record_ref(intent)
    audit.record(session, actor.ctx.external_user_id, family.id, "estate_intent.import", "estate_intent", ref, True, "allowed")
    events.emit(
        session,
        family,
        "estate_intent.extracted.v1",
        ref,
        {"intent_ref": ref, "instrument_ref": ins["ref"], "fixture_ref": fixture_ref},
        idempotency_key=f"estate_intent.extracted.v1:{family.id}:{fixture_ref}",
    )
    return [intent]


def _current_conflicting_peers(session: Session, intent: TransferIntent) -> list[TransferIntent]:
    """Other intents on the same asset that are verified or already contested, still current, and name someone else."""
    return list(
        session.scalars(
            select(TransferIntent).where(
                TransferIntent.family_id == intent.family_id,
                TransferIntent.asset_id == intent.asset_id,
                TransferIntent.id != intent.id,
                TransferIntent.status.in_(("verified", "contested")),
                TransferIntent.valid_to.is_(None),
                TransferIntent.beneficiary_person_id != intent.beneficiary_person_id,
            )
        )
    )


def _restore_uncontested(session: Session, family_id, asset_id) -> None:
    """Contested intents on an asset become verified again once one beneficiary is left among its current intents."""
    session.flush()
    current = list(
        session.scalars(
            select(TransferIntent).where(
                TransferIntent.family_id == family_id,
                TransferIntent.asset_id == asset_id,
                TransferIntent.status.in_(("verified", "contested")),
                TransferIntent.valid_to.is_(None),
            )
        )
    )
    if len({i.beneficiary_person_id for i in current}) == 1:
        for intent in current:
            intent.status = "verified"


def verify(
    actor: FamilyActor,
    session: Session,
    intent_id: str,
    verified: bool,
    notes: str | None,
    source_version: int,
) -> TransferIntent:
    """Advisor decision on a proposed intent. Rejecting leaves it `proposed`, unverified, with the notes."""
    require_role(actor, "advisor")
    intent = lookup.family_record(session, actor, TransferIntent, intent_id)
    instrument = session.get(LegalInstrument, intent.instrument_id)
    source = session.get(SourceDocument, instrument.source_document_id) if instrument else None
    if source_version != (source.revision if source else 0):
        raise ApiError(409, "stale_source", "The source document changed since you opened it. Reload and review again.")
    if intent.status != "proposed":
        raise ApiError(409, "invalid_transition", f"A {intent.status} intent cannot be verified.")

    ref = record_ref(intent)
    intent.verification_notes = notes
    if not verified:
        intent.advisor_verified = False
        outcome = "proposed"
    else:
        intent.advisor_verified = True
        intent.verified_by = actor.person.id
        intent.verified_at = _now()
        peers = _current_conflicting_peers(session, intent)
        outcome = "contested" if peers else "verified"
        for peer in peers:
            peer.status = "contested"
        if instrument is not None and instrument.status in ("draft", "reported"):
            instrument.status = "verified"
    intent.status = outcome

    audit.record(
        session, actor.ctx.external_user_id, actor.family.id, "estate_intent.verify", "estate_intent", ref, True, outcome
    )
    events.emit(
        session,
        actor.family,
        "estate_intent.verified.v1",
        ref,
        {"intent_ref": ref, "verified": verified, "status": outcome},
    )
    return intent


def set_instrument_status(
    actor: FamilyActor, session: Session, instrument_id: str, status: Literal["superseded"]
) -> LegalInstrument:
    """Mark an instrument superseded: its intents end today and stop earning an `INTENDED_FOR` edge."""
    require_role(actor, "advisor")
    instrument = lookup.family_record(session, actor, LegalInstrument, instrument_id)
    today = date.today()
    intents = list(session.scalars(select(TransferIntent).where(TransferIntent.instrument_id == instrument.id)))
    for intent in intents:
        intent.status = "superseded"
        intent.valid_to = max(today, intent.valid_from or today)
    instrument.status = status
    for asset_id in {intent.asset_id for intent in intents}:
        _restore_uncontested(session, actor.family.id, asset_id)

    ref = record_ref(instrument)
    audit.record(
        session, actor.ctx.external_user_id, actor.family.id, "instrument.set_status", "instrument", ref, True, status
    )
    events.emit(session, actor.family, "instrument.status_changed.v1", ref, {"instrument_ref": ref, "status": status})
    return instrument


def mark_counsel_reviewed(actor: FamilyActor, session: Session, intent_id: str) -> TransferIntent:
    """Record that estate counsel reviewed the intent's instrument (a parent may do so for their own assets)."""
    require_role(actor, "advisor", "parent")
    intent = lookup.family_record(session, actor, TransferIntent, intent_id)
    if actor.role == "parent":
        asset = session.get(Asset, intent.asset_id)
        if asset is None or asset.owner_person_id != actor.person.id:
            raise ApiError(404, "not_found", "Record not found.")
    instrument = session.get(LegalInstrument, intent.instrument_id)
    instrument.counsel_reviewed_at = _now()
    instrument.reviewed_date = date.today()

    ref = record_ref(intent)
    audit.record(
        session, actor.ctx.external_user_id, actor.family.id, "estate_intent.counsel_reviewed", "estate_intent", ref, True, "allowed"
    )
    events.emit(
        session, actor.family, "estate_intent.counsel_reviewed.v1", ref, {"intent_ref": ref}
    )
    return intent
