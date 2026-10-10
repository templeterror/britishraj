"""Load the synthetic Morgan and Chen fixtures into the heirloom tables.

`reset_and_seed` is destructive and idempotent: it clears every heirloom row (including runtime
rows such as audit log and events) and reloads the fixtures with deterministic ids.
"""

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.heirloom.ids import ref_id
from app.heirloom.models import (
    Asset,
    Base,
    DecisionRecord,
    Family,
    FamilyPerson,
    HeirGoal,
    LegalInstrument,
    SourceDocument,
    TransferIntent,
)

FIXTURE_DIR = Path(__file__).resolve().parent.parent / "fixtures"
FAMILY_FIXTURES = ("morgan_family.json", "chen_family.json")


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURE_DIR / name).read_text())


def _date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def _datetime(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value).replace(tzinfo=UTC) if value else None


def _clear(session: Session) -> None:
    session.expunge_all()  # the bulk deletes below bypass the identity map
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(delete(table))
    session.flush()


def _load_family(session: Session, data: dict) -> None:
    org = data["organization_id"]
    spec = data["family"]
    family_id = ref_id(spec["ref"])
    scope = {"organization_id": org, "family_id": family_id}

    session.add(
        Family(
            id=family_id,
            organization_id=org,
            external_ref=spec["ref"],
            display_name=spec["display_name"],
            as_of_year=spec["as_of_year"],
            preserve_values=list(spec["preserve_values"]),
        )
    )
    session.flush()

    for p in data.get("people", []):
        session.add(
            FamilyPerson(
                id=ref_id(p["ref"]),
                external_ref=p["ref"],
                external_user_id=p.get("external_user_id"),
                display_name=p["display_name"],
                family_role=p["family_role"],
                age=p.get("age"),
                **scope,
            )
        )
    for s in data.get("sources", []):
        text = (FIXTURE_DIR / s["file"]).read_bytes()
        session.add(
            SourceDocument(
                id=ref_id(s["ref"]),
                external_ref=s["ref"],
                source_type=s["source_type"],
                title=s["title"],
                storage_key=s["file"],
                document_date=_date(s["document_date"]),
                checksum=hashlib.sha256(text).hexdigest(),
                **scope,
            )
        )
    session.flush()

    for a in data.get("assets", []):
        session.add(
            Asset(
                id=ref_id(a["ref"]),
                external_ref=a["ref"],
                owner_person_id=ref_id(a["owner"]) if a.get("owner") else None,
                asset_type=a["asset_type"],
                label=a["label"],
                as_of_date=_date(a["as_of_date"]),
                estimated_value=a["estimated_value"],
                liabilities=a["liabilities"],
                liquidity_class=a["liquidity_class"],
                verified_status="verified",
                terms=dict(a["terms"]),
                **scope,
            )
        )
    for i in data.get("instruments", []):
        session.add(
            LegalInstrument(
                id=ref_id(i["ref"]),
                external_ref=i["ref"],
                instrument_type=i["instrument_type"],
                title=i["title"],
                effective_date=_date(i["effective_date"]),
                revocable=i["revocable"],
                status=i["status"],
                source_document_id=ref_id(i["source"]),
                **scope,
            )
        )
    session.flush()

    for t in data.get("intents", []):
        session.add(
            TransferIntent(
                id=ref_id(t["ref"]),
                external_ref=t["ref"],
                instrument_id=ref_id(t["instrument"]),
                asset_id=ref_id(t["asset"]),
                beneficiary_person_id=ref_id(t["beneficiary"]),
                allocation_description=t["allocation_description"],
                conditions=list(t["conditions"]),
                advisor_verified=t["advisor_verified"],
                verified_by=ref_id(t["verified_by"]) if t.get("verified_by") else None,
                verified_at=_datetime(t.get("verified_at")),
                confidence=t["confidence"],
                status=t["status"],
                valid_from=_date(t["valid_from"]),
                valid_to=_date(t["valid_to"]),
                **scope,
            )
        )

    advisor = session.scalars(
        select(FamilyPerson).where(FamilyPerson.family_id == family_id, FamilyPerson.family_role == "advisor")
    ).first()
    asset_owner = {a["ref"]: a.get("owner") for a in data.get("assets", [])}

    for d in data.get("decisions", []):
        session.add(
            DecisionRecord(
                id=ref_id(d["ref"]),
                external_ref=d["ref"],
                asset_id=ref_id(d["asset"]),
                person_id=ref_id(asset_owner[d["asset"]]),
                advisor_person_id=advisor.id,
                decision_date=_date(d["decision_date"]),
                action_text=d["action_text"],
                rationale_text=d["rationale_text"],
                source_document_id=ref_id(d["source"]),
                source_locator=dict(d["locator"]),
                extraction_confidence=1.0,
                verification_status="verified",
                verified_by=advisor.id,
                valid_from=_date(d["decision_date"]),
                valid_to=_date(d["valid_to"]),
                **scope,
            )
        )
    # Candidates arrive in the blueprint CandidateDecision shape (what the decision-analysis provider
    # returns). The decision's person is the asset's owner and its advisor the family's advisor.
    for c in data.get("candidate_decisions", []):
        ref = data["candidate_decision_refs"][c["external_event_id"]]
        source = c["source"]
        session.add(
            DecisionRecord(
                id=ref_id(ref),
                external_ref=ref,
                external_event_id=c["external_event_id"],
                asset_id=ref_id(c["asset_ref"]),
                person_id=ref_id(asset_owner[c["asset_ref"]]),
                advisor_person_id=advisor.id,
                decision_date=_date(c["decision_date"]),
                action_text=c["decision_summary"],
                rationale_text=c["documented_rationale"],
                alternatives=list(c["alternatives"]),
                source_document_id=ref_id(source["source_id"]),
                source_locator={
                    "start_seconds": source["start_seconds"],
                    "end_seconds": source["end_seconds"],
                    "quoted_span": source["excerpt"],
                },
                extraction_confidence=c["confidence"],
                verification_status=c["status"],
                valid_from=_date(c["decision_date"]),
                **scope,
            )
        )

    for g in data.get("goals", []):
        session.add(
            HeirGoal(
                id=ref_id(g["ref"]),
                external_ref=g["ref"],
                heir_person_id=ref_id(g["heir"]),
                goal_kind=g["goal_kind"],
                description_private=g["description_private"],
                amount_target=g["amount_target"],
                target_year=g["target_year"],
                horizon_min_years=g["horizon_min_years"],
                horizon_max_years=g["horizon_max_years"],
                milestone=g["milestone"],
                goal_funding_source=g["goal_funding_source"],
                **scope,
            )
        )
    session.flush()


def reset_and_seed(session: Session) -> None:
    _clear(session)
    for name in FAMILY_FIXTURES:
        _load_family(session, load_fixture(name))
    session.commit()
