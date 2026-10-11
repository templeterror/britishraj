"""Task 17: the family advisor records Robert's sharing instructions from a cited conversation.

Robert stays the grantor; Sarah is only `recorded_by`. James's own goal consent stays James-only, and
the basis note Sarah writes is advisor-only: it never reaches any heir-facing response.
"""

from datetime import date

import pytest
from conftest import auth
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.heirloom.ids import ref_id
from app.heirloom.models import AuditLog, ConsentGrant, SourceDocument

MORGAN = ref_id("demo-morgan")
CHEN = ref_id("family-chen")
BASE = f"/api/v1/families/{MORGAN}"
SARAH = ref_id("person-sarah")
ROBERT = ref_id("person-robert")
JAMES = ref_id("person-james")
GOAL = ref_id("goal-james-business")
RETAIN = ref_id("decision-retain-llc")  # a candidate until Sarah verifies it
RESERVE = ref_id("decision-liquidity-reserve")
INTENT = ref_id("intent-james-llc")
TRANSCRIPT = ref_id("meeting-2026-04-15")

NOTE = "Robert asked that James can read why we kept the LLC interest"
BASIS = {"conversation_date": "2026-04-15", "note": NOTE, "source_ref": "meeting-2026-04-15"}
STOP_NOTE = "Robert would like to pause this until the family meeting"
STOP_BASIS = {"conversation_date": "2026-05-01", "note": STOP_NOTE, "source_ref": None}
REASON = "advisor_recorded_client_instruction"


def _get(client: TestClient, persona: str, path: str):
    return client.get(f"{BASE}{path}", headers=auth(client, persona))


def _snapshot(client: TestClient, persona: str) -> dict:
    response = _get(client, persona, "/snapshot")
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _consent(client: TestClient, persona: str, resource, scope: str, recipient, active=True, basis=None):
    body = {"scope": scope, "recipient_person_id": str(recipient), "active": active}
    if basis is not None:
        body["basis"] = basis
    return client.put(f"{BASE}/consents/{resource}", headers=auth(client, persona), json=body)


def _verify_retain(client: TestClient) -> None:
    response = client.post(
        f"{BASE}/decisions/decision-retain-llc/verify", headers=auth(client, "sarah"), json={"approved": True}
    )
    assert response.status_code == 200, response.text


def _record(client: TestClient, active: bool = True, basis: dict | None = None) -> dict:
    response = _consent(client, "sarah", RETAIN, "decision_excerpt", JAMES, active, basis or BASIS)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _consent_revision(client: TestClient) -> int:
    return _get(client, "sarah", "/revision").json()["data"]["consent_revision"]


def _approved_ids(client: TestClient) -> list[str]:
    return [d["decision_id"] for d in _snapshot(client, "james")["approved_decisions"]]


def _advisor_decision(client: TestClient, ref: str) -> dict:
    return {d["ref"]: d for d in _snapshot(client, "sarah")["decisions"]}[ref]


def _error(response) -> str:
    return response.json()["errors"][0]["code"]


def _grant(db_session: Session, resource) -> ConsentGrant:
    db_session.expire_all()
    return db_session.scalars(
        select(ConsentGrant).where(
            ConsentGrant.resource_id == resource, ConsentGrant.share_scope == "decision_excerpt"
        )
    ).one()


def test_advisor_records_share_with_basis(client: TestClient, db_session: Session):
    _verify_retain(client)
    before = _consent_revision(client)

    state = _record(client)
    assert state["grant"]["active"] is True
    assert state["consent_revision"] == before + 1

    grant = _grant(db_session, RETAIN)
    assert grant.grantor_person_id == ROBERT
    assert grant.recipient_person_id == JAMES
    assert grant.recorded_by == "demo_sarah"
    assert grant.recorded_via == "advisor_recorded"
    assert grant.basis_note == NOTE
    assert grant.basis_date == date(2026, 4, 15)
    assert grant.basis_source_id == TRANSCRIPT
    assert _consent_revision(client) == before + 1

    assert str(RETAIN) in _approved_ids(client)
    sharing = _advisor_decision(client, "decision-retain-llc")["heir_sharing"]
    assert sharing["shared"] is True
    assert sharing["recipient_person_id"] == str(JAMES)
    assert sharing["recipient_display"] == "James Morgan"
    assert sharing["recorded_via"] == "advisor_recorded"
    assert sharing["recorded_by_display"] == "Sarah Lin"
    assert sharing["basis_date"] == "2026-04-15"
    assert sharing["basis_note"] == NOTE
    assert sharing["basis_source_ref"] == "meeting-2026-04-15"
    assert sharing["basis_source_title"]
    assert sharing["updated_at"] is not None

    parent = {d["ref"]: d for d in _snapshot(client, "robert")["decisions"]}
    assert parent["decision-retain-llc"]["shared_with_heir"] is True  # Robert is still the grantor

    row = db_session.scalars(select(AuditLog).where(AuditLog.reason_code == REASON)).one()
    assert row.actor_external_id == "demo_sarah"
    assert row.allowed is True
    assert row.action == "consent.set"


def test_basis_required_and_validated(client: TestClient, db_session: Session):
    _verify_retain(client)
    before = _consent_revision(client)

    missing = _consent(client, "sarah", RETAIN, "decision_excerpt", JAMES)
    assert missing.status_code == 422
    assert _error(missing) == "basis_required"
    stop_missing = _consent(client, "sarah", RETAIN, "decision_excerpt", JAMES, active=False)
    assert stop_missing.status_code == 422
    assert _error(stop_missing) == "basis_required"

    for bad_date in ("2099-01-01", "1999-12-31"):
        response = _consent(
            client, "sarah", RETAIN, "decision_excerpt", JAMES, basis={**BASIS, "conversation_date": bad_date}
        )
        assert response.status_code == 422, bad_date
        assert _error(response) == "invalid_basis_date", bad_date

    db_session.add(
        SourceDocument(
            organization_id="org_other",
            family_id=CHEN,
            external_ref="chen-transcript",
            source_type="transcript",
            title="Another family's transcript",
            storage_key="none.txt",
            document_date=date(2026, 1, 1),
            checksum="0" * 64,
        )
    )
    db_session.commit()
    # Unknown, an estate instrument rather than a conversation, or another family's transcript.
    for ref in ("nope", "source-estate-letter-2026", "chen-transcript"):
        response = _consent(
            client, "sarah", RETAIN, "decision_excerpt", JAMES, basis={**BASIS, "source_ref": ref}
        )
        assert response.status_code == 422, ref
        assert _error(response) == "unknown_source", ref

    for note in ("   ", "x" * 501):
        response = _consent(client, "sarah", RETAIN, "decision_excerpt", JAMES, basis={**BASIS, "note": note})
        assert response.status_code == 422

    assert _consent_revision(client) == before
    assert _approved_ids(client) == []
    assert db_session.scalars(select(ConsentGrant)).all() == []


def test_basis_without_source_ref_is_accepted(client: TestClient, db_session: Session):
    _verify_retain(client)
    _record(client, basis={"conversation_date": "2026-04-15", "note": f"  {NOTE}  "})
    grant = _grant(db_session, RETAIN)
    assert grant.basis_note == NOTE  # stripped
    assert grant.basis_source_id is None
    sharing = _advisor_decision(client, "decision-retain-llc")["heir_sharing"]
    assert (sharing["basis_source_ref"], sharing["basis_source_title"]) == (None, None)


@pytest.mark.parametrize("active", [True, False])
@pytest.mark.parametrize("scope", ["goal_summary", "goal_detail"])
def test_advisor_cannot_record_heir_goal_consent_403(
    client: TestClient, db_session: Session, scope: str, active: bool
):
    response = _consent(client, "sarah", GOAL, scope, SARAH, active, BASIS)
    assert response.status_code == 403
    assert _error(response) == "forbidden_for_role"
    assert _consent_revision(client) == 0
    advisor = _snapshot(client, "sarah")
    assert advisor["goal_sharing"] == "not_shared"
    assert advisor["shared_goals"] == []
    assert _snapshot(client, "james")["sharing"] == {"advisor_summary": False, "advisor_detail": False}
    assert db_session.scalars(select(ConsentGrant)).all() == []
    denied = db_session.scalars(select(AuditLog).where(AuditLog.allowed.is_(False))).one()
    assert denied.actor_external_id == "demo_sarah"


@pytest.mark.parametrize("scope", ["estate_intent", "balances"])
def test_advisor_estate_intent_and_balances_rejected_422(client: TestClient, scope: str):
    for resource in (INTENT, RESERVE):
        response = _consent(client, "sarah", resource, scope, JAMES, basis=BASIS)
        assert response.status_code == 422
        assert _error(response) == "not_available_in_pilot"
    assert _consent_revision(client) == 0


def test_advisor_records_stop_sharing(client: TestClient, db_session: Session):
    _verify_retain(client)
    _record(client)
    assert str(RETAIN) in _approved_ids(client)
    before = _consent_revision(client)

    state = _record(client, active=False, basis=STOP_BASIS)
    assert state["grant"]["active"] is False
    assert state["consent_revision"] == before + 1
    assert str(RETAIN) not in _approved_ids(client)
    assert _get(client, "james", "/evidence/decision-retain-llc").status_code == 404

    sharing = _advisor_decision(client, "decision-retain-llc")["heir_sharing"]
    assert sharing["shared"] is False
    assert sharing["recorded_via"] == "advisor_recorded"
    assert sharing["recorded_by_display"] == "Sarah Lin"
    assert sharing["basis_date"] == "2026-05-01"
    assert sharing["basis_note"] == STOP_NOTE
    assert (sharing["basis_source_ref"], sharing["basis_source_title"]) == (None, None)
    assert sharing["updated_at"] is not None

    grant = _grant(db_session, RETAIN)
    assert (grant.grantor_person_id, grant.active, grant.revoked_at is not None) == (ROBERT, False, True)
    reasons = db_session.scalars(select(AuditLog.reason_code).where(AuditLog.action == "consent.set")).all()
    assert reasons == [REASON, REASON]


def test_basis_note_never_reaches_heir(client: TestClient):
    _verify_retain(client)
    _record(client)
    responses = {
        "snapshot": _get(client, "james", "/snapshot"),
        "ask": client.post(
            f"{BASE}/memory/ask",
            headers=auth(client, "james"),
            json={"question": "Why was family control important?"},
        ),
        "preview": _get(client, "sarah", "/heir-preview"),
        "graph": _get(client, "james", "/graph"),
        "evidence": _get(client, "james", "/evidence/decision-retain-llc"),
    }
    assert responses["ask"].json()["data"]["status"] == "answered"
    assert [m["decision_id"] for m in responses["ask"].json()["data"]["matches"]] == [str(RETAIN)]
    for name, response in responses.items():
        assert response.status_code == 200, (name, response.text)
        assert NOTE not in response.text, name
        assert "Robert asked" not in response.text, name
        assert "basis" not in response.text, name
        assert "recorded_via" not in response.text, name
    # The parent DTO is unchanged too (its own fixture quotes contain "Robert asked", so check the note).
    parent = _get(client, "robert", "/snapshot")
    assert NOTE not in parent.text
    assert "basis" not in parent.text


def test_heir_preview_for_advisor_matches_heir_view(client: TestClient):
    _verify_retain(client)
    _record(client)
    assert _consent(client, "robert", RESERVE, "decision_excerpt", JAMES).status_code == 200

    preview = _get(client, "sarah", "/heir-preview")
    assert preview.status_code == 200, preview.text
    approved = preview.json()["data"]["approved_decisions"]
    assert approved == _snapshot(client, "james")["approved_decisions"]
    assert approved == _get(client, "robert", "/heir-preview").json()["data"]["approved_decisions"]
    assert [d["decision_id"] for d in approved] == [str(RESERVE), str(RETAIN)]
    assert preview.headers["cache-control"] == "no-store"


def test_heir_preview_heir_403(client: TestClient):
    response = _get(client, "james", "/heir-preview")
    assert response.status_code == 403
    assert _error(response) == "forbidden_for_role"


def test_other_org_advisor_404(client: TestClient):
    _verify_retain(client)
    response = _consent(client, "other_advisor", RETAIN, "decision_excerpt", JAMES, basis=BASIS)
    assert response.status_code == 404
    assert _error(response) == "family_not_found"
    preview = _get(client, "other_advisor", "/heir-preview")
    assert preview.status_code == 404
    assert _consent_revision(client) == 0
    assert _approved_ids(client) == []


def test_candidate_decision_cannot_be_shared(client: TestClient):
    response = _consent(client, "sarah", RETAIN, "decision_excerpt", JAMES, basis=BASIS)
    assert response.status_code == 403
    assert _error(response) == "consent_not_permitted"
    assert _consent_revision(client) == 0
    assert _approved_ids(client) == []
    assert _advisor_decision(client, "decision-retain-llc")["heir_sharing"] is None


@pytest.mark.parametrize(
    ("resource", "recipient"),
    [
        (RESERVE, SARAH),  # decisions go to an adult heir only
        (RESERVE, ROBERT),
        (ref_id("no-such-record"), JAMES),
        (GOAL, JAMES),  # not a decision
    ],
)
def test_advisor_other_decision_combinations_403(client: TestClient, resource, recipient):
    response = _consent(client, "sarah", resource, "decision_excerpt", recipient, basis=BASIS)
    assert response.status_code == 403
    assert _error(response) == "consent_not_permitted"
    assert _consent_revision(client) == 0


def test_parent_self_grant_still_works_without_basis(client: TestClient, db_session: Session):
    response = _consent(client, "robert", RESERVE, "decision_excerpt", JAMES)
    assert response.status_code == 200, response.text
    grant = _grant(db_session, RESERVE)
    assert (grant.grantor_person_id, grant.recorded_by, grant.recorded_via) == (ROBERT, "demo_robert", "self")
    assert (grant.basis_note, grant.basis_date, grant.basis_source_id) == (None, None, None)

    sharing = _advisor_decision(client, "decision-liquidity-reserve")["heir_sharing"]
    assert sharing["shared"] is True
    assert sharing["recorded_via"] == "self"
    assert sharing["recorded_by_display"] == "Robert Morgan"
    assert (sharing["basis_date"], sharing["basis_note"], sharing["basis_source_ref"]) == (None, None, None)
    reasons = db_session.scalars(select(AuditLog.reason_code).where(AuditLog.action == "consent.set")).all()
    assert reasons == ["granted"]


def test_parent_self_grant_stores_supplied_basis(client: TestClient, db_session: Session):
    basis = {
        "conversation_date": "2023-11-09",
        "note": "Shared after our review",
        "source_ref": "source-note-2023-11-09",
    }
    response = _consent(client, "robert", RESERVE, "decision_excerpt", JAMES, basis=basis)
    assert response.status_code == 200, response.text
    grant = _grant(db_session, RESERVE)
    assert grant.recorded_via == "self"
    assert grant.basis_note == "Shared after our review"
    assert grant.basis_source_id == ref_id("source-note-2023-11-09")
    bad = _consent(
        client, "robert", RESERVE, "decision_excerpt", JAMES, False, {**basis, "source_ref": "nope"}
    )
    assert bad.status_code == 422
    assert _error(bad) == "unknown_source"


def test_advisor_snapshot_has_sources_policy_and_preserve_values(client: TestClient):
    data = _snapshot(client, "sarah")
    sources = {s["ref"]: s for s in data["sources"]}
    assert sources["meeting-2026-04-15"]["source_type"] == "transcript"
    assert (
        sources["meeting-2026-04-15"]["title"]
        == "Meeting transcript, Robert Morgan and Sarah Lin, 2026-04-15"
    )
    assert sources["meeting-2026-04-15"]["document_date"] == "2026-04-15"
    assert {s["source_type"] for s in data["sources"]} == {"transcript", "meeting_note"}
    assert "source-estate-letter-2026" not in sources
    dates = [s["document_date"] for s in data["sources"]]
    assert dates == sorted(dates, reverse=True)
    assert len(data["sources"]) == 5
    assert data["sharing_policy"] == {"estate_intent": "off", "balances": "not_available_in_pilot"}
    assert data["preserve_values"] == [
        "Family control of the business",
        "Avoid forced sales",
        "Long-term growth",
        "Charitable purpose",
    ]

    decisions = {d["ref"]: d for d in data["decisions"]}
    assert decisions["decision-retain-llc"]["heir_sharing"] is None  # a candidate is not shareable
    sharing = decisions["decision-liquidity-reserve"]["heir_sharing"]
    assert sharing == {
        "shared": False,
        "recipient_person_id": str(JAMES),
        "recipient_display": "James Morgan",
        "recorded_via": None,
        "recorded_by_display": None,
        "basis_date": None,
        "basis_note": None,
        "basis_source_ref": None,
        "basis_source_title": None,
        "updated_at": None,
    }


def test_actor_fields_in_body_are_ignored(client: TestClient, db_session: Session):
    """A forged grantor, recorder or role in the body changes nothing: the actor is resolved server-side."""
    _verify_retain(client)
    response = client.put(
        f"{BASE}/consents/{RETAIN}",
        headers=auth(client, "sarah"),
        json={
            "scope": "decision_excerpt",
            "recipient_person_id": str(JAMES),
            "active": True,
            "basis": BASIS,
            "grantor_person_id": str(SARAH),
            "recorded_by": "demo_robert",
            "recorded_via": "self",
            "role": "parent",
        },
    )
    assert response.status_code == 200, response.text
    grant = _grant(db_session, RETAIN)
    assert (grant.grantor_person_id, grant.recorded_by, grant.recorded_via) == (
        ROBERT,
        "demo_sarah",
        "advisor_recorded",
    )


def test_parent_change_after_advisor_record_replaces_provenance(client: TestClient, db_session: Session):
    """Provenance always describes the latest change: Robert's own stop clears Sarah's basis."""
    _verify_retain(client)
    _record(client)
    response = _consent(client, "robert", RETAIN, "decision_excerpt", JAMES, active=False)
    assert response.status_code == 200, response.text

    grant = _grant(db_session, RETAIN)  # still one row: Robert is the grantor of both changes
    assert (grant.recorded_via, grant.recorded_by, grant.basis_note) == ("self", "demo_robert", None)
    sharing = _advisor_decision(client, "decision-retain-llc")["heir_sharing"]
    assert sharing["shared"] is False
    assert (sharing["recorded_via"], sharing["recorded_by_display"]) == ("self", "Robert Morgan")
    assert (sharing["basis_note"], sharing["basis_date"], sharing["basis_source_ref"]) == (None, None, None)


@pytest.mark.parametrize("scope", ["goal_summary", "goal_detail"])
def test_heir_cannot_probe_sources_through_goal_basis(
    client: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch, scope: str
):
    """A basis is only for `decision_excerpt`: on James's goal grant it is rejected before any lookup,
    so the response cannot reveal which advisor/parent conversation records exist."""
    from app.heirloom.services import consent

    def no_lookup(*_args, **_kwargs):
        raise AssertionError("the heir must never trigger a source lookup")

    monkeypatch.setattr(consent, "_basis_source", no_lookup)
    responses = [
        _consent(client, "james", GOAL, scope, SARAH, basis={**BASIS, "source_ref": ref})
        for ref in ("meeting-2026-04-15", "meeting-2030-01-01")
    ]
    for response in responses:
        assert response.status_code == 422, response.text
        assert _error(response) == "basis_not_allowed"
    assert responses[0].json() == responses[1].json()
    assert _consent_revision(client) == 0
    assert db_session.scalars(select(ConsentGrant)).all() == []

    response = _consent(client, "james", GOAL, scope, SARAH)
    assert response.status_code == 200, response.text
    db_session.expire_all()
    rows = db_session.scalars(select(ConsentGrant).where(ConsentGrant.resource_id == GOAL)).all()
    assert {row.share_scope for row in rows} == (
        {"goal_summary", "goal_detail"} if scope == "goal_detail" else {scope}
    )
    for row in rows:
        assert (row.basis_note, row.basis_date, row.basis_source_id) == (None, None, None)
        assert row.recorded_via == "self"
        assert row.grantor_person_id == JAMES


def test_basis_rejected_on_any_non_decision_scope(client: TestClient):
    response = _consent(client, "robert", RESERVE, "asset_identity", JAMES, basis=BASIS)
    assert response.status_code == 422
    assert _error(response) == "basis_not_allowed"
    assert _consent_revision(client) == 0


def test_heir_decision_excerpt_with_basis_never_looks_up_sources(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    """James cannot grant a decision excerpt; with a basis he gets the same 403 whatever he cites."""
    from app.heirloom.services import consent

    def no_lookup(*_args, **_kwargs):
        raise AssertionError("the heir must never trigger a source lookup")

    monkeypatch.setattr(consent, "_basis_source", no_lookup)
    responses = [
        _consent(client, "james", RESERVE, "decision_excerpt", JAMES, basis={**BASIS, "source_ref": ref})
        for ref in ("meeting-2026-04-15", "meeting-2030-01-01")
    ]
    for response in responses:
        assert response.status_code == 403
        assert _error(response) == "consent_not_permitted"
    assert responses[0].json() == responses[1].json()
