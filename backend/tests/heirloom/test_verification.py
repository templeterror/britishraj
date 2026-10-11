from datetime import date

from conftest import auth
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.heirloom.ids import ref_id
from app.heirloom.models import (
    AuditLog,
    DecisionRecord,
    DomainEvent,
    FamilyPerson,
    LegalInstrument,
    TransferIntent,
)

MORGAN = ref_id("demo-morgan")
CHEN = ref_id("family-chen")
BASE = f"/api/v1/families/{MORGAN}"
CURRENT_INTENT = ref_id("intent-james-llc")
LETTER = ref_id("instr-estate-letter-2026")
CANDIDATE = ref_id("decision-retain-llc")
VERIFIED_DECISION = ref_id("decision-liquidity-reserve")


def _import(client: TestClient, persona: str = "sarah"):
    return client.post(
        f"{BASE}/estate-intents/import",
        headers=auth(client, persona),
        json={"fixture_ref": "conflicting_amendment"},
    )


def _amendment(client: TestClient) -> dict:
    response = _import(client)
    assert response.status_code == 200, response.text
    (intent,) = response.json()["data"]
    return intent


def _verify_intent(client: TestClient, intent_id: str, *, version: int | None = None, verified=True):
    return client.post(
        f"{BASE}/estate-intents/{intent_id}/verify",
        headers=auth(client, "sarah"),
        json={"verified": verified, "notes": "Checked against the source.", "source_version": version or 1},
    )


def _graph(client: TestClient, persona: str = "sarah") -> dict:
    response = client.get(f"{BASE}/graph", headers=auth(client, persona))
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _intended_for(graph: dict) -> list[tuple[str, str]]:
    return [(e["source_id"], e["target_id"]) for e in graph["edges"] if e["type"] == "INTENDED_FOR"]


def _intent_statuses(client: TestClient) -> dict[str, str]:
    snapshot = client.get(f"{BASE}/snapshot", headers=auth(client, "sarah")).json()["data"]
    return {i["id"]: i["status"] for i in snapshot["intents"]}


def _verify_decision(client: TestClient, persona: str, decision_id, **body):
    payload = {"approved": True, "edited_rationale": None, "note": None, **body}
    return client.post(f"{BASE}/decisions/{decision_id}/verify", headers=auth(client, persona), json=payload)


def test_imported_amendment_is_candidate_and_no_edge(client: TestClient):
    intent = _amendment(client)
    assert intent["status"] == "proposed"
    assert intent["advisor_verified"] is False
    assert intent["beneficiary_display_name"] == "Claire Morgan"
    assert intent["asset_ref"] == "asset-family-llc"

    graph = _graph(client)
    assert _intended_for(graph) == [("intent-james-llc", "person-james")]
    nodes = {n["record_id"]: n for n in graph["nodes"]}
    assert nodes[intent["ref"]]["evidence_status"] == "candidate"


def test_import_twice_returns_the_same_candidate(client: TestClient):
    first = _amendment(client)
    second = _amendment(client)
    assert first["id"] == second["id"]
    assert len(_intent_statuses(client)) == 3


def test_import_emits_extracted_event(client: TestClient, db_session: Session):
    _amendment(client)
    types = list(db_session.scalars(select(DomainEvent.type)))
    assert "estate_intent.extracted.v1" in types


def test_amendment_beneficiary_is_hidden_from_the_heir(client: TestClient):
    _amendment(client)
    assert "Claire" not in str(_graph(client, "james"))
    assert "Claire" in str(_graph(client, "robert"))


def test_verifying_conflicting_amendment_contests_both(client: TestClient):
    intent = _amendment(client)
    response = _verify_intent(client, intent["id"])
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "contested"
    assert response.json()["data"]["advisor_verified"] is True

    statuses = _intent_statuses(client)
    assert statuses[str(CURRENT_INTENT)] == "contested"
    assert statuses[intent["id"]] == "contested"
    assert _intended_for(_graph(client)) == []


def test_verifying_non_conflicting_intent_is_verified_with_edge(client: TestClient, db_session: Session):
    intent = _amendment(client)
    letter_intent = db_session.get(TransferIntent, CURRENT_INTENT)
    letter_intent.status = "superseded"  # no longer current: nothing for the amendment to conflict with
    db_session.commit()

    response = _verify_intent(client, intent["id"])
    assert response.json()["data"]["status"] == "verified"
    assert _intended_for(_graph(client)) == [(intent["ref"], "person-claire")]


def _third_proposed_intent(client: TestClient, db_session: Session, amendment: dict) -> TransferIntent:
    """A further proposed intent on the LLC naming a beneficiary different from both existing ones."""
    letter_intent = db_session.get(TransferIntent, CURRENT_INTENT)
    heir = FamilyPerson(
        id=ref_id("person-dana"),
        external_ref="person-dana",
        display_name="Dana Morgan",
        family_role="other",
        organization_id=letter_intent.organization_id,
        family_id=letter_intent.family_id,
    )
    db_session.add(heir)
    db_session.flush()
    third = TransferIntent(
        id=ref_id("intent-dana-llc"),
        external_ref="intent-dana-llc",
        instrument_id=ref_id("instr-amendment-2026"),
        asset_id=letter_intent.asset_id,
        beneficiary_person_id=heir.id,
        allocation_description="Robert's 40% membership interest",
        conditions=[],
        advisor_verified=False,
        status="proposed",
        valid_from=date(2026, 9, 2),
        organization_id=letter_intent.organization_id,
        family_id=letter_intent.family_id,
    )
    db_session.add(third)
    db_session.commit()
    return third


def test_third_differing_intent_on_a_contested_asset_is_contested(client: TestClient, db_session: Session):
    amendment = _amendment(client)
    assert _verify_intent(client, amendment["id"]).json()["data"]["status"] == "contested"
    third = _third_proposed_intent(client, db_session, amendment)

    response = _verify_intent(client, str(third.id))
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "contested"
    statuses = _intent_statuses(client)
    assert [statuses[i] for i in (str(CURRENT_INTENT), amendment["id"], str(third.id))] == ["contested"] * 3
    assert _intended_for(_graph(client)) == []


def test_superseding_a_competing_instrument_restores_the_survivor(client: TestClient):
    amendment = _amendment(client)
    _verify_intent(client, amendment["id"])
    assert _intent_statuses(client)[amendment["id"]] == "contested"

    response = client.post(
        f"{BASE}/instruments/{LETTER}/status", headers=auth(client, "sarah"), json={"status": "superseded"}
    )
    assert response.status_code == 200, response.text
    statuses = _intent_statuses(client)
    assert statuses[str(CURRENT_INTENT)] == "superseded"
    assert statuses[amendment["id"]] == "verified"
    assert _intended_for(_graph(client)) == [(amendment["ref"], "person-claire")]


def test_superseding_one_of_three_keeps_the_rest_contested(client: TestClient, db_session: Session):
    amendment = _amendment(client)
    _verify_intent(client, amendment["id"])
    third = _third_proposed_intent(client, db_session, amendment)
    _verify_intent(client, str(third.id))

    client.post(f"{BASE}/instruments/{LETTER}/status", headers=auth(client, "sarah"), json={"status": "superseded"})
    statuses = _intent_statuses(client)
    assert statuses[amendment["id"]] == "contested"
    assert statuses[str(third.id)] == "contested"
    assert _intended_for(_graph(client)) == []


def test_rejecting_candidate_keeps_it_proposed_with_notes(client: TestClient):
    intent = _amendment(client)
    response = _verify_intent(client, intent["id"], verified=False)
    data = response.json()["data"]
    assert data["status"] == "proposed"
    assert data["advisor_verified"] is False
    assert data["verification_notes"] == "Checked against the source."
    assert _intent_statuses(client)[str(CURRENT_INTENT)] == "verified"
    assert len(_intended_for(_graph(client))) == 1


def test_superseding_2026_letter_removes_edge(client: TestClient):
    response = client.post(
        f"{BASE}/instruments/{LETTER}/status", headers=auth(client, "sarah"), json={"status": "superseded"}
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["status"] == "superseded"
    assert _intent_statuses(client)[str(CURRENT_INTENT)] == "superseded"
    assert _intended_for(_graph(client)) == []


def test_superseding_sets_valid_to_today(client: TestClient, db_session: Session):
    client.post(f"{BASE}/instruments/{LETTER}/status", headers=auth(client, "sarah"), json={"status": "superseded"})
    db_session.expire_all()
    assert db_session.get(TransferIntent, CURRENT_INTENT).valid_to == date.today()
    assert db_session.get(LegalInstrument, LETTER).status == "superseded"


def test_stale_source_version_409(client: TestClient):
    intent = _amendment(client)
    response = _verify_intent(client, intent["id"], version=7)
    assert response.status_code == 409
    assert response.json()["errors"][0]["code"] == "stale_source"
    assert _intent_statuses(client)[intent["id"]] == "proposed"


def test_heir_cannot_verify_intent_403(client: TestClient):
    intent = _amendment(client)
    response = client.post(
        f"{BASE}/estate-intents/{intent['id']}/verify",
        headers=auth(client, "james"),
        json={"verified": True, "notes": None, "source_version": 1},
    )
    assert response.status_code == 403
    assert _intent_statuses(client)[intent["id"]] == "proposed"


def test_heir_cannot_import_or_supersede(client: TestClient):
    assert _import(client, "james").status_code == 403
    response = client.post(
        f"{BASE}/instruments/{LETTER}/status", headers=auth(client, "james"), json={"status": "superseded"}
    )
    assert response.status_code == 403


def test_other_orgs_advisor_cannot_import_404(client: TestClient):
    response = client.post(
        f"/api/v1/families/{MORGAN}/estate-intents/import",
        headers=auth(client, "other_advisor"),
        json={"fixture_ref": "conflicting_amendment"},
    )
    assert response.status_code == 404


def test_unknown_fixture_ref_422(client: TestClient):
    response = client.post(
        f"{BASE}/estate-intents/import", headers=auth(client, "sarah"), json={"fixture_ref": "nope"}
    )
    assert response.status_code == 422


def test_parent_counsel_reviewed_sets_timestamp(client: TestClient):
    intent = _amendment(client)
    assert intent["counsel_reviewed_at"] is None
    response = client.post(f"{BASE}/estate-intents/{intent['id']}/counsel-reviewed", headers=auth(client, "robert"))
    assert response.status_code == 200, response.text
    assert response.json()["data"]["counsel_reviewed_at"] is not None


def test_heir_cannot_mark_counsel_reviewed(client: TestClient):
    response = client.post(f"{BASE}/estate-intents/{CURRENT_INTENT}/counsel-reviewed", headers=auth(client, "james"))
    assert response.status_code == 403


def test_decision_verify_candidate_to_verified(client: TestClient, db_session: Session):
    response = _verify_decision(client, "sarah", CANDIDATE)
    assert response.status_code == 200, response.text
    data = response.json()["data"]
    assert data["verification_status"] == "verified"
    assert data["verified_by_display"] == "Sarah Lin"
    assert data["rationale_edited"] is False

    nodes = {n["record_id"]: n for n in _graph(client)["nodes"]}
    assert nodes["decision-retain-llc"]["evidence_status"] == "verified"
    audit = db_session.scalars(select(AuditLog).where(AuditLog.action == "decision.verify")).all()
    assert [(a.actor_external_id, a.resource_id, a.allowed) for a in audit] == [
        ("demo_sarah", "decision-retain-llc", True)
    ]
    assert "decision.verified.v1" in list(db_session.scalars(select(DomainEvent.type)))


def test_decision_reject_requires_note_422(client: TestClient, db_session: Session):
    response = _verify_decision(client, "sarah", CANDIDATE, approved=False)
    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "note_required"
    assert db_session.get(DecisionRecord, CANDIDATE).verification_status == "candidate"


def test_decision_reject_with_note(client: TestClient):
    response = _verify_decision(client, "sarah", CANDIDATE, approved=False, note="Not what Robert said.")
    data = response.json()["data"]
    assert data["verification_status"] == "rejected"
    assert data["advisor_note"] == "Not what Robert said."
    assert "decision-retain-llc" not in {n["record_id"] for n in _graph(client)["nodes"]}


def test_cannot_verify_already_verified_409(client: TestClient):
    seeded = _verify_decision(client, "sarah", VERIFIED_DECISION)  # verified in the seed data
    assert seeded.status_code == 409
    assert seeded.json()["errors"][0]["code"] == "invalid_transition"

    assert _verify_decision(client, "sarah", CANDIDATE).status_code == 200
    again = _verify_decision(client, "sarah", CANDIDATE, approved=False, note="changed my mind")
    assert again.status_code == 409
    assert again.json()["errors"][0]["code"] == "invalid_transition"


def test_edited_rationale_marks_edited(client: TestClient):
    response = _verify_decision(client, "sarah", CANDIDATE, edited_rationale="Keep control; avoid a forced sale.")
    data = response.json()["data"]
    assert data["rationale"] == "Keep control; avoid a forced sale."
    assert data["rationale_edited"] is True


def test_parent_cannot_verify_decision_403(client: TestClient, db_session: Session):
    response = _verify_decision(client, "robert", CANDIDATE)
    assert response.status_code == 403
    assert response.json()["errors"][0]["code"] == "forbidden_for_role"
    assert db_session.get(DecisionRecord, CANDIDATE).verification_status == "candidate"


def test_advisor_annotate(client: TestClient):
    response = client.post(
        f"{BASE}/decisions/{CANDIDATE}/annotate", headers=auth(client, "sarah"), json={"note": "Ask about the LLC debt."}
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["advisor_note"] == "Ask about the LLC debt."
    assert client.post(
        f"{BASE}/decisions/{CANDIDATE}/annotate", headers=auth(client, "robert"), json={"note": "x"}
    ).status_code == 403


def test_blank_note_is_rejected_and_keeps_the_existing_note(client: TestClient, db_session: Session):
    advisor, parent = auth(client, "sarah"), auth(client, "robert")
    url = f"{BASE}/decisions/{CANDIDATE}"
    client.post(f"{url}/annotate", headers=advisor, json={"note": "Ask about the LLC debt."})
    events_before = len(list(db_session.scalars(select(DomainEvent.type))))

    for route, headers in (("annotate", advisor), ("request-correction", parent)):
        response = client.post(f"{url}/{route}", headers=headers, json={"note": "   \n\t "})
        assert response.status_code == 422, response.text
        assert response.json()["errors"][0]["code"] == "note_required"

    db_session.expire_all()
    assert db_session.get(DecisionRecord, CANDIDATE).advisor_note == "Ask about the LLC debt."
    assert len(list(db_session.scalars(select(DomainEvent.type)))) == events_before


def test_parent_request_correction(client: TestClient, db_session: Session):
    response = client.post(
        f"{BASE}/decisions/{CANDIDATE}/request-correction",
        headers=auth(client, "robert"),
        json={"note": "I said partner consent, not control."},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["advisor_note"] == "I said partner consent, not control."
    assert "decision.correction_requested.v1" in list(db_session.scalars(select(DomainEvent.type)))
    # advisors and heirs cannot use the parent's route
    for persona in ("sarah", "james"):
        denied = client.post(
            f"{BASE}/decisions/{CANDIDATE}/request-correction", headers=auth(client, persona), json={"note": "x"}
        )
        assert denied.status_code == 403


def test_decision_in_another_family_is_404(client: TestClient):
    response = client.post(
        f"/api/v1/families/{CHEN}/decisions/{CANDIDATE}/verify",
        headers=auth(client, "other_advisor"),
        json={"approved": True},
    )
    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "not_found"


def test_list_decisions_filters_by_status(client: TestClient):
    response = client.get(f"{BASE}/decisions", headers=auth(client, "sarah"), params={"status": "candidate"})
    assert [d["ref"] for d in response.json()["data"]] == ["decision-retain-llc"]
    everything = client.get(f"{BASE}/decisions", headers=auth(client, "sarah")).json()["data"]
    assert len(everything) == 5
    assert client.get(f"{BASE}/decisions", headers=auth(client, "sarah"), params={"status": "bogus"}).status_code == 422
    assert client.get(f"{BASE}/decisions", headers=auth(client, "james")).json()["data"] == []
