import re

import pytest
from conftest import auth
from fastapi.testclient import TestClient

from app.heirloom.dto.advisor import AdvisorGoalSummary
from app.heirloom.dto.heir import HeirDecisionView
from app.heirloom.ids import ref_id
from app.heirloom.services import consent, snapshots

MORGAN = ref_id("demo-morgan")
GOAL_ID = ref_id("goal-james-business")
RESERVE_ID = ref_id("decision-liquidity-reserve")


def _snapshot(client: TestClient, persona: str):
    response = client.get(f"/api/v1/families/{MORGAN}/snapshot", headers=auth(client, persona))
    assert response.status_code == 200, response.text
    return response


def _keys(value) -> set[str]:
    """Every object key anywhere in a decoded JSON document."""
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in _keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _keys(v)}
    return set()


def _has_number(text: str, number: int) -> bool:
    """True when `number` appears as a whole numeric token (5000000 does not contain 500000)."""
    return re.search(rf"(?<!\d){number}(?!\d)", text) is not None


def test_advisor_snapshot_has_no_goal_when_not_shared(client: TestClient):
    response = _snapshot(client, "sarah")
    body = response.json()
    data = body["data"]

    assert data["goal_sharing"] == "not_shared"
    assert data["shared_goals"] == []
    assert not _has_number(response.text, 500000)
    assert '"500000"' not in response.text
    assert "software company" not in response.text

    # The advisor still sees the estate side in full.
    assert data["advisor"]["display_name"] == "Sarah Lin"
    assets = {a["ref"]: a for a in data["assets"]}
    assert set(assets) == {"asset-family-llc", "asset-public-stock", "asset-brokerage"}
    assert assets["asset-family-llc"]["value"] == 5000000
    assert assets["asset-family-llc"]["liabilities"] == 1200000
    assert assets["asset-family-llc"]["terms"]["liquidatable_fraction"] == 0.25
    assert all(a["market_events"] == [] for a in data["assets"])
    assert {i["ref"] for i in data["intents"]} == {"intent-2024-llc-split", "intent-james-llc"}
    assert {i["ref"] for i in data["instruments"]} == {"instr-draft-will-2024", "instr-estate-letter-2026"}
    statuses = {d["ref"]: d["verification_status"] for d in data["decisions"]}
    assert len(statuses) == 5
    assert statuses["decision-retain-llc"] == "candidate"
    assert data["coverage"] == {
        "decisions_verified": 4,
        "decisions_total": 5,
        "assets_with_verified_intent": 1,
        "assets_total": 3,
        "heirs_connected": 0,
        "heirs_total": 1,
    }
    assert data["open_flags"] == 0
    assert body["meta"]["mode"] == "demo"
    assert body["meta"]["consent_revision"] == 0


def test_heir_snapshot_has_no_estate_or_balances(client: TestClient):
    response = _snapshot(client, "james")
    data = response.json()["data"]

    assert not _keys(data) & {"assets", "intents", "instruments"}
    for forbidden in ("LLC", "5000000", "intent-", "Holdings"):
        assert forbidden not in response.text, forbidden

    assert data["family"] == {"id": str(MORGAN), "display_name": "Morgan family"}
    assert data["me"]["display_name"] == "James Morgan"
    assert data["advisor"] == {"display_name": "Sarah Lin"}
    assert [g["ref"] for g in data["my_goals"]] == ["goal-james-business"]
    assert data["my_goals"][0]["description_private"].startswith("Build a software company")
    assert data["sharing"] == {"advisor_summary": False, "advisor_detail": False}
    assert data["approved_decisions"] == []
    assert data["invitations"] == []
    assert 2 <= len(data["planning_prompts"]) <= 3


def test_parent_snapshot_never_contains_heir_goal(client: TestClient):
    response = _snapshot(client, "robert")
    data = response.json()["data"]

    assert "software company" not in response.text
    assert not _keys(data) & {"my_goals", "shared_goals"}

    assert data["me"]["display_name"] == "Robert Morgan"
    assert {a["ref"] for a in data["assets"]} == {"asset-family-llc", "asset-public-stock", "asset-brokerage"}
    assert all(a["value"] for a in data["assets"])
    assert len(data["decisions"]) == 5
    assert all(d["shared_with_heir"] is False for d in data["decisions"])
    assert all("counsel_reviewed_at" in i for i in data["intents"])
    assert data["preserve_values"][0] == "Family control of the business"
    assert data["heirs"] == [{"person_id": str(ref_id("person-james")), "display_name": "James Morgan"}]
    assert data["sharing"] == {
        "decision_excerpts": 0,
        "estate_intent": "off",
        "balances": "not_available_in_pilot",
    }


@pytest.mark.parametrize("persona", ["sarah", "robert", "james"])
def test_snapshot_cache_control_no_store(client: TestClient, persona: str):
    assert _snapshot(client, persona).headers["cache-control"] == "no-store"


def test_snapshot_role_comes_from_membership_not_query(client: TestClient):
    response = client.get(
        f"/api/v1/families/{MORGAN}/snapshot?view=advisor&role=advisor", headers=auth(client, "james")
    )
    assert "assets" not in response.json()["data"]


def test_cross_org_snapshot_is_404(client: TestClient):
    response = client.get(f"/api/v1/families/{MORGAN}/snapshot", headers=auth(client, "other_advisor"))
    assert response.status_code == 404


def test_advisor_goal_visibility_goes_through_consent_gate(client: TestClient, monkeypatch):
    """Task 6 fills `goal_view_for_advisor`; the snapshot must take whatever it returns, verbatim."""
    summary = AdvisorGoalSummary(
        goal_id=str(GOAL_ID),
        kind="business",
        horizon_band="8–12 years",
        amount_band="about $500K",
        amount_band_mid=500000,
        horizon_max_years=12,
    )
    monkeypatch.setattr(consent, "goal_view_for_advisor", lambda _s, _f, _g: summary)

    data = _snapshot(client, "sarah").json()["data"]
    assert data["goal_sharing"] == "summary"
    assert data["shared_goals"] == [summary.model_dump(mode="json")]
    assert data["coverage"]["heirs_connected"] == 1
    assert "software company" not in str(data)


def test_heir_approved_decisions_drive_heir_and_parent_views(client: TestClient, monkeypatch):
    view = HeirDecisionView(
        decision_id=str(RESERVE_ID),
        date="2023-11-09",
        title="Build a two-year liquidity reserve",
        rationale="Robert wanted enough near-term cash.",
        source_title="Advisor meeting note, 2023-11-09",
        locator={"page": 1},
        verified_by_display="Sarah Lin",
        asset_kind="cash",
    )
    monkeypatch.setattr(snapshots, "heir_approved_decisions", lambda _s, _f, _p: [view])

    heir = _snapshot(client, "james").json()["data"]
    assert heir["approved_decisions"] == [view.model_dump(mode="json")]

    parent = _snapshot(client, "robert").json()["data"]
    shared = {d["ref"]: d["shared_with_heir"] for d in parent["decisions"]}
    assert shared["decision-liquidity-reserve"] is True
    assert sum(shared.values()) == 1
    assert parent["sharing"]["decision_excerpts"] == 1
