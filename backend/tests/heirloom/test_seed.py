import json
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from app.heirloom import db as heirloom_db
from app.heirloom.ids import NAMESPACE, ref_id
from app.heirloom.models import (
    Asset,
    AuditLog,
    ConsentGrant,
    DecisionRecord,
    Family,
    FamilyPerson,
    HeirGoal,
    LegalInstrument,
    TransferIntent,
)
from app.heirloom.services.seed import FIXTURE_DIR, reset_and_seed

ORG = "org_relay_demo"


def _count(session: Session, model, family: Family) -> int:
    return session.scalar(select(func.count()).select_from(model).where(model.family_id == family.id))


def _morgan(session: Session) -> Family:
    return session.scalars(select(Family).where(Family.external_ref == "demo-morgan")).one()


def test_ref_id_is_deterministic():
    assert ref_id("asset-family-llc") == ref_id("asset-family-llc")
    assert ref_id("asset-family-llc") != ref_id("asset-public-stock")
    assert ref_id("asset-family-llc") == uuid.uuid5(NAMESPACE, "asset-family-llc")


def test_seed_counts(db_session: Session):
    reset_and_seed(db_session)
    morgan = _morgan(db_session)
    assert morgan.id == ref_id("demo-morgan")
    assert morgan.organization_id == ORG
    assert morgan.display_name == "Morgan family"
    assert morgan.as_of_year == 2026
    assert morgan.data_revision == 0 and morgan.consent_revision == 0
    assert morgan.preserve_values == [
        "Family control of the business",
        "Avoid forced sales",
        "Long-term growth",
        "Charitable purpose",
    ]
    assert _count(db_session, FamilyPerson, morgan) == 3
    assert _count(db_session, Asset, morgan) == 3
    assert _count(db_session, LegalInstrument, morgan) == 2
    assert _count(db_session, TransferIntent, morgan) == 2
    assert _count(db_session, DecisionRecord, morgan) == 5
    assert _count(db_session, HeirGoal, morgan) == 1
    assert _count(db_session, ConsentGrant, morgan) == 0

    statuses = dict(
        db_session.execute(
            select(DecisionRecord.external_ref, DecisionRecord.verification_status).where(
                DecisionRecord.family_id == morgan.id
            )
        ).all()
    )
    assert sorted(v for v in statuses.values()) == ["candidate"] + ["verified"] * 4
    assert statuses["decision-retain-llc"] == "candidate"

    chen = db_session.scalars(select(Family).where(Family.external_ref == "family-chen")).one()
    assert chen.organization_id == "org_other"
    people = db_session.scalars(select(FamilyPerson).where(FamilyPerson.family_id == chen.id)).all()
    assert [p.external_user_id for p in people] == ["demo_other_advisor"]
    assert _count(db_session, Asset, chen) == 1


def test_seed_personas_and_assets(db_session: Session):
    reset_and_seed(db_session)
    morgan = _morgan(db_session)
    people = {
        p.external_ref: p
        for p in db_session.scalars(select(FamilyPerson).where(FamilyPerson.family_id == morgan.id))
    }
    assert {k: (v.external_user_id, v.family_role) for k, v in people.items()} == {
        "person-sarah": ("demo_sarah", "advisor"),
        "person-robert": ("demo_robert", "parent"),
        "person-james": ("demo_james", "adult_heir"),
    }
    assert people["person-james"].age == 29

    llc = db_session.get(Asset, ref_id("asset-family-llc"))
    assert llc.owner_person_id == people["person-robert"].id
    assert (llc.estimated_value, llc.liabilities, llc.liquidity_class) == (5_000_000, 1_200_000, "illiquid")
    assert llc.terms["liquidatable_fraction"] == 0.25
    assert llc.terms["sale_delay_years"] == 2
    assert llc.terms["partner_consent_required"] is True
    assert llc.terms["partner_consent_process_documented"] is True
    assert set(llc.terms) == {
        "expected_return",
        "annual_volatility",
        "annual_fee",
        "liquidatable_fraction",
        "sale_delay_years",
        "admin_delay_years",
        "sale_cost_fraction",
        "distribution_yield",
        "admin_cost_fraction",
        "partner_consent_required",
        "partner_consent_process_documented",
    }


def test_seed_intents_follow_the_documents(db_session: Session):
    reset_and_seed(db_session)
    current = db_session.get(TransferIntent, ref_id("intent-james-llc"))
    assert current.status == "verified" and current.advisor_verified is True
    assert current.verified_by == ref_id("person-sarah")
    assert current.valid_to is None
    assert current.beneficiary_person_id == ref_id("person-james")
    assert current.instrument_id == ref_id("instr-estate-letter-2026")
    old = db_session.get(TransferIntent, ref_id("intent-2024-llc-split"))
    assert old.status == "superseded" and str(old.valid_to) == "2026-03-02"
    assert db_session.get(LegalInstrument, ref_id("instr-draft-will-2024")).status == "superseded"
    assert db_session.get(LegalInstrument, ref_id("instr-estate-letter-2026")).revocable is True


def test_seed_is_idempotent(db_session: Session):
    def snapshot() -> dict:
        morgan = _morgan(db_session)
        return {
            m.__name__: _count(db_session, m, morgan)
            for m in (FamilyPerson, Asset, LegalInstrument, TransferIntent, DecisionRecord, HeirGoal)
        }

    reset_and_seed(db_session)
    first = snapshot()
    first_id = db_session.scalars(
        select(TransferIntent.id).where(TransferIntent.external_ref == "intent-james-llc")
    ).one()
    reset_and_seed(db_session)
    assert snapshot() == first
    assert db_session.scalars(select(func.count()).select_from(Family)).one() == 2
    second_id = db_session.scalars(
        select(TransferIntent.id).where(TransferIntent.external_ref == "intent-james-llc")
    ).one()
    assert first_id == second_id == ref_id("intent-james-llc")


def test_reset_drops_runtime_rows(db_session: Session):
    reset_and_seed(db_session)
    morgan = _morgan(db_session)
    morgan.consent_revision = 4
    db_session.add(
        AuditLog(
            organization_id=ORG,
            actor_external_id="demo_sarah",
            action="x",
            resource_type="y",
            allowed=True,
            reason_code="ok",
        )
    )
    db_session.commit()
    reset_and_seed(db_session)
    assert _morgan(db_session).consent_revision == 0
    assert db_session.scalar(select(func.count()).select_from(AuditLog)) == 0


def test_candidate_decision_has_locator(db_session: Session):
    reset_and_seed(db_session)
    decision = db_session.get(DecisionRecord, ref_id("decision-retain-llc"))
    assert decision.verification_status == "candidate"
    assert decision.verified_by is None
    assert decision.action_text == "Keep the family LLC interest rather than force a sale"
    assert decision.rationale_text == (
        "Retain family control of the business and avoid a forced sale in unfavorable conditions"
    )
    assert decision.alternatives == [
        "Sell part of the interest",
        "Refinance the LLC debt",
        "Retain the holding",
    ]
    assert decision.extraction_confidence == 0.91
    assert decision.asset_id == ref_id("asset-family-llc")
    assert decision.person_id == ref_id("person-robert")
    assert decision.advisor_person_id == ref_id("person-sarah")
    assert str(decision.decision_date) == "2026-04-15"
    assert decision.source_locator["start_seconds"] == 113
    assert decision.source_locator["end_seconds"] == 148
    transcript = (FIXTURE_DIR / "meeting_2026_04_15.txt").read_text()
    assert decision.source_locator["quoted_span"] == (
        "We want to keep control of the business in the family. "
        "I don't want to be forced to sell when the timing is wrong."
    )
    assert decision.source_locator["quoted_span"] in transcript


def test_candidate_fixture_block_has_blueprint_shape():
    morgan = json.loads((FIXTURE_DIR / "morgan_family.json").read_text())
    (block,) = morgan["candidate_decisions"]
    assert set(block) == {
        "schema_version",
        "external_event_id",
        "family_id",
        "asset_ref",
        "decision_date",
        "decision_summary",
        "documented_rationale",
        "alternatives",
        "source",
        "confidence",
        "status",
    }
    assert set(block["source"]) == {"source_id", "start_seconds", "end_seconds", "excerpt"}
    assert block["status"] == "candidate" and block["family_id"] == "demo-morgan"


def test_every_decision_locator_quotes_its_source(db_session: Session):
    from app.heirloom.models import SourceDocument

    reset_and_seed(db_session)
    for decision in db_session.scalars(
        select(DecisionRecord).where(DecisionRecord.family_id == ref_id("demo-morgan"))
    ):
        source = db_session.get(SourceDocument, decision.source_document_id)
        text = (FIXTURE_DIR / source.storage_key).read_text()
        assert decision.source_locator["quoted_span"] in text, decision.external_ref


def test_goal_is_james_private_goal(db_session: Session):
    reset_and_seed(db_session)
    goal = db_session.get(HeirGoal, ref_id("goal-james-business"))
    assert goal.heir_person_id == ref_id("person-james")
    assert (goal.goal_kind, goal.amount_target, goal.target_year) == ("business", 500_000, 2038)
    assert (goal.horizon_min_years, goal.horizon_max_years) == (8, 12)
    assert goal.goal_funding_source == "unknown"
    assert goal.version == 1
    assert goal.description_private.startswith("Build a software company")


def test_fixture_files_are_short_and_present():
    for name in (
        "morgan_family.json",
        "chen_family.json",
        "market_events.json",
        "meeting_2026_04_15.txt",
        "estate_letter_2026.txt",
        "draft_will_2024.txt",
        "conflicting_amendment.txt",
    ):
        path = FIXTURE_DIR / name
        assert path.is_file(), name
        if name.endswith(".txt"):
            assert len(path.read_text().splitlines()) <= 40, name
    assert "Claire Morgan (Robert's niece)" in (FIXTURE_DIR / "conflicting_amendment.txt").read_text()
    assert "First Amendment" in (FIXTURE_DIR / "conflicting_amendment.txt").read_text()
    events = json.loads((FIXTURE_DIR / "market_events.json").read_text())
    assert [(e["asset_ref"], e["proposed_stress"], e["published_at"]) for e in events] == [
        ("asset-public-stock", "shock_30_y1", "2026-08-07")
    ]


def test_external_ref_unique_per_family(db_session: Session):
    reset_and_seed(db_session)
    morgan = _morgan(db_session)
    db_session.add(
        FamilyPerson(
            organization_id=ORG,
            family_id=morgan.id,
            external_ref="person-james",
            display_name="Dup",
            family_role="other",
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_enum_values_are_enforced(db_session: Session):
    reset_and_seed(db_session)
    decision = db_session.get(DecisionRecord, ref_id("decision-retain-llc"))
    decision.verification_status = "bogus"
    with pytest.raises(StatementError):
        db_session.flush()
    db_session.rollback()


def test_app_startup_seeds_demo_database(db_session: Session):
    # `client` (via db_session) started the app, which seeds an empty demo DB.
    refs = set(db_session.scalars(select(Family.external_ref)))
    assert refs == {"demo-morgan", "family-chen"}


def _session_app() -> tuple[FastAPI, Engine]:
    engine = heirloom_db.make_engine("sqlite://")
    heirloom_db.init_db(engine)
    app = FastAPI()
    app.state.engine = engine

    @app.post("/families/{family_id}")
    def create(family_id: str, session: heirloom_db.SessionDep):
        session.add(
            Family(
                organization_id="o",
                display_name=family_id,
                external_ref=family_id,
                as_of_year=2026,
            )
        )

    @app.get("/families")
    def list_families(session: heirloom_db.SessionDep):
        return sorted(session.scalars(select(Family.external_ref)))

    @app.post("/boom")
    def boom(session: heirloom_db.SessionDep):
        session.add(Family(organization_id="o", display_name="boom", external_ref="boom", as_of_year=2026))
        session.flush()
        raise RuntimeError("fail")

    return app, engine


def test_session_dep_commits_on_success_and_rolls_back_on_handler_error():
    app, engine = _session_app()
    with TestClient(app, raise_server_exceptions=False) as c:
        assert c.post("/families/ok").status_code == 200
        assert c.post("/boom").status_code == 500
    with Session(engine) as s:
        assert list(s.scalars(select(Family.external_ref))) == ["ok"]


def test_session_dep_write_is_visible_to_the_next_request():
    app, _ = _session_app()
    with TestClient(app) as c:
        assert c.post("/families/a").status_code == 200
        assert c.get("/families").json() == ["a"]


def test_session_dep_failing_commit_returns_500_and_rolls_back(monkeypatch):
    app, engine = _session_app()
    rollbacks: list[bool] = []
    original_rollback = Session.rollback

    def spy_rollback(self):
        rollbacks.append(True)
        return original_rollback(self)

    monkeypatch.setattr(Session, "rollback", spy_rollback)
    with TestClient(app, raise_server_exceptions=False) as c:
        assert c.post("/families/dup").status_code == 200
        # Same unique external_ref: the INSERT only runs at commit time, which must fail the request.
        assert c.post("/families/dup").status_code == 500
        assert c.get("/families").json() == ["dup"]
    assert rollbacks
    with Session(engine) as s:
        assert list(s.scalars(select(Family.external_ref))) == ["dup"]
