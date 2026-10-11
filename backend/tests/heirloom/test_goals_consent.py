import pytest
from conftest import auth
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.heirloom.ids import ref_id
from app.heirloom.models import AdvisorAction, Family, Insight

MORGAN = ref_id("demo-morgan")
BASE = f"/api/v1/families/{MORGAN}"
GOAL = ref_id("goal-james-business")
SARAH = ref_id("person-sarah")
ROBERT = ref_id("person-robert")
JAMES = ref_id("person-james")
RESERVE = ref_id("decision-liquidity-reserve")
CANDIDATE = ref_id("decision-retain-llc")
INTENT = ref_id("intent-james-llc")


def _keys(value) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in _keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in _keys(v)}
    return set()


def _get(client: TestClient, persona: str, path: str):
    return client.get(f"{BASE}{path}", headers=auth(client, persona))


def _snapshot(client: TestClient, persona: str) -> dict:
    response = _get(client, persona, "/snapshot")
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _consent(client: TestClient, persona: str, resource, scope: str, recipient, active: bool = True):
    return client.put(
        f"{BASE}/consents/{resource}",
        headers=auth(client, persona),
        json={"scope": scope, "recipient_person_id": str(recipient), "active": active},
    )


def _share_goal(client: TestClient, scope: str, active: bool = True) -> dict:
    response = _consent(client, "james", GOAL, scope, SARAH, active)
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _patch_goal(client: TestClient, version: int = 1, **fields):
    return client.patch(
        f"{BASE}/heir-goals/{GOAL}", headers=auth(client, "james"), json={"version": version, **fields}
    )


def _consent_revision(client: TestClient) -> int:
    return _get(client, "sarah", "/revision").json()["data"]["consent_revision"]


def test_goal_saved_private_by_default(client: TestClient):
    response = _patch_goal(client, description_private="Open a bakery in Portland.", amount_target=300000)
    assert response.status_code == 200, response.text
    goal = response.json()["data"]
    assert goal["version"] == 2
    assert goal["description_private"] == "Open a bakery in Portland."
    assert goal["amount_target"] == 300000
    assert goal["target_year"] == 2038  # fields not sent are kept

    advisor = _get(client, "sarah", "/snapshot")
    assert advisor.json()["data"]["goal_sharing"] == "not_shared"
    assert advisor.json()["data"]["shared_goals"] == []
    assert "bakery" not in advisor.text
    assert _snapshot(client, "james")["sharing"] == {"advisor_summary": False, "advisor_detail": False}
    assert _consent_revision(client) == 0


def test_heir_creates_goal_privately_and_only_heirs_create(client: TestClient):
    body = {
        "goal_kind": "philanthropy",
        "description_private": "Endow a small family foundation",
        "amount_target": 250000,
        "target_year": 2051,
        "horizon_min_years": 20,
        "horizon_max_years": 25,
    }
    response = client.post(f"{BASE}/heir-goals", headers=auth(client, "james"), json=body)
    assert response.status_code == 200, response.text
    created = response.json()["data"]
    assert created["goal_kind"] == "philanthropy"
    assert created["version"] == 1
    assert created["goal_funding_source"] == "unknown"

    assert len(_snapshot(client, "james")["my_goals"]) == 2
    assert _snapshot(client, "sarah")["goal_sharing"] == "not_shared"
    for persona in ("sarah", "robert"):
        denied = client.post(f"{BASE}/heir-goals", headers=auth(client, persona), json=body)
        assert denied.status_code == 403, persona


def test_summary_share_exposes_bands_only(client: TestClient):
    state = _share_goal(client, "goal_summary")
    assert state["grant"]["active"] is True
    assert state["grant"]["scope"] == "goal_summary"
    assert state["consent_revision"] == 1

    response = _get(client, "sarah", "/snapshot")
    data = response.json()["data"]
    assert data["goal_sharing"] == "summary"
    (goal,) = data["shared_goals"]
    assert goal["goal_id"] == str(GOAL)
    assert goal["kind"] == "business"
    assert goal["amount_band"] == "about $500K"
    assert goal["horizon_band"] == "8–12 years"
    assert goal["amount_band_mid"] == 500000
    assert not {"description", "amount_target", "target_year", "milestone"} & set(goal)
    assert not {"description", "amount_target", "description_private"} & _keys(data)
    assert "software company" not in response.text
    assert data["coverage"]["heirs_connected"] == 1
    assert response.json()["meta"]["consent_revision"] == 1


def test_detail_share_implies_summary_and_revoke_summary_revokes_detail(client: TestClient):
    _share_goal(client, "goal_detail")
    advisor = _snapshot(client, "sarah")
    assert advisor["goal_sharing"] == "detail"
    (goal,) = advisor["shared_goals"]
    assert goal["amount_target"] == 500000
    assert goal["target_year"] == 2038
    assert goal["milestone"] == "Incorporate and raise a pre-seed round"
    assert goal["description"].startswith("Build a software company")
    assert goal["amount_band"] == "about $500K"
    assert _snapshot(client, "james")["sharing"] == {"advisor_summary": True, "advisor_detail": True}

    _share_goal(client, "goal_detail", active=False)  # detail off keeps the summary
    assert _snapshot(client, "sarah")["goal_sharing"] == "summary"
    _share_goal(client, "goal_detail")

    _share_goal(client, "goal_summary", active=False)
    advisor = _snapshot(client, "sarah")
    assert advisor["goal_sharing"] == "not_shared"
    assert advisor["shared_goals"] == []
    assert _snapshot(client, "james")["sharing"] == {"advisor_summary": False, "advisor_detail": False}


def test_revocation_removes_goal_from_every_advisor_endpoint(client: TestClient):
    before = _consent_revision(client)
    _share_goal(client, "goal_summary")
    assert _get(client, "sarah", "/evidence/goal-james-business").status_code == 200
    graph = _get(client, "sarah", "/graph").json()["data"]
    assert "goal-james-business" in {n["record_id"] for n in graph["nodes"]}

    _share_goal(client, "goal_summary", active=False)
    responses = {
        "snapshot": _get(client, "sarah", "/snapshot"),
        "graph": _get(client, "sarah", "/graph"),
        "evidence": _get(client, "sarah", "/evidence/goal-james-business"),
    }
    assert responses["snapshot"].status_code == 200
    assert responses["graph"].status_code == 200
    assert responses["evidence"].status_code == 404
    for name, response in responses.items():
        assert str(GOAL) not in response.text, name
        assert "about $500K" not in response.text, name
        if name != "evidence":
            assert "goal-james-business" not in response.text, name
    assert _consent_revision(client) == before + 2


def test_version_conflict_409(client: TestClient):
    first = _patch_goal(client, version=1, milestone="Ship a prototype")
    assert first.status_code == 200, first.text
    second = _patch_goal(client, version=1, milestone="Hire a cofounder")
    assert second.status_code == 409
    assert second.json()["errors"][0]["code"] == "version_conflict"

    (goal,) = _snapshot(client, "james")["my_goals"]
    assert goal["milestone"] == "Ship a prototype"
    assert goal["version"] == 2


@pytest.mark.parametrize(
    "fields",
    [
        {"amount_target": 0},
        {"amount_target": -5},
        {"amount_target": 1_000_000_001},
        {"target_year": 2020},
        {"target_year": 2026},
        {"target_year": 2077},
        {"description_private": "   "},
        {"goal_kind": None},
        {"horizon_min_years": 12, "horizon_max_years": 8},
    ],
)
def test_goal_validation_422(client: TestClient, fields: dict):
    response = _patch_goal(client, **fields)
    assert response.status_code == 422, response.text
    (goal,) = _snapshot(client, "james")["my_goals"]
    assert goal["version"] == 1
    assert goal["amount_target"] == 500000


def test_goal_patch_is_owner_only(client: TestClient):
    for persona in ("sarah", "robert"):
        response = client.patch(f"{BASE}/heir-goals/{GOAL}", headers=auth(client, persona), json={"version": 1})
        assert response.status_code == 403, persona


@pytest.mark.parametrize("scope", ["estate_intent", "balances"])
def test_estate_intent_scope_rejected(client: TestClient, scope: str):
    response = _consent(client, "robert", INTENT, scope, JAMES)
    assert response.status_code == 422
    assert response.json()["errors"][0]["code"] == "not_available_in_pilot"
    assert _consent_revision(client) == 0


def test_parent_cannot_share_candidate_decision_403(client: TestClient):
    response = _consent(client, "robert", CANDIDATE, "decision_excerpt", JAMES)
    assert response.status_code == 403
    assert _consent_revision(client) == 0
    assert _snapshot(client, "james")["approved_decisions"] == []


def test_heir_cannot_grant_decision_excerpt_403(client: TestClient):
    response = _consent(client, "james", RESERVE, "decision_excerpt", JAMES)
    assert response.status_code == 403
    assert _snapshot(client, "james")["approved_decisions"] == []


@pytest.mark.parametrize(
    ("persona", "resource", "scope", "recipient"),
    [
        ("james", GOAL, "goal_summary", ROBERT),  # goals go to the advisor only
        ("sarah", GOAL, "goal_summary", SARAH),  # only the heir shares their goal
        ("robert", GOAL, "goal_detail", SARAH),
        ("robert", RESERVE, "decision_excerpt", SARAH),  # decisions go to an adult heir only
        ("robert", RESERVE, "goal_summary", SARAH),  # scope does not match the resource
        ("robert", RESERVE, "asset_identity", JAMES),
        ("james", ref_id("no-such-record"), "goal_summary", SARAH),
    ],
)
def test_other_grant_combinations_403(client: TestClient, persona, resource, scope, recipient):
    response = _consent(client, persona, resource, scope, recipient)
    assert response.status_code == 403, response.text
    assert _consent_revision(client) == 0


def test_heir_preview_matches_heir_view(client: TestClient):
    response = _consent(client, "robert", RESERVE, "decision_excerpt", JAMES)
    assert response.status_code == 200, response.text

    preview = _get(client, "robert", "/heir-preview")
    assert preview.status_code == 200, preview.text
    heir = _get(client, "james", "/snapshot")
    approved = preview.json()["data"]["approved_decisions"]
    assert approved == heir.json()["data"]["approved_decisions"]
    assert [d["decision_id"] for d in approved] == [str(RESERVE)]
    assert approved[0]["title"] == "Build a two-year liquidity reserve"
    assert approved[0]["verified_by_display"] == "Sarah Lin"
    for text in (preview.text, heir.text):
        assert "3100000" not in text
        assert "Diversified brokerage account" not in text

    parent = _snapshot(client, "robert")
    shared = {d["ref"]: d["shared_with_heir"] for d in parent["decisions"]}
    assert shared["decision-liquidity-reserve"] is True
    assert sum(shared.values()) == 1
    assert _get(client, "james", "/heir-preview").status_code == 403
    # Task 17: the advisor sees the same heir preview (to record Robert's instructions on her page).
    advisor_preview = _get(client, "sarah", "/heir-preview")
    assert advisor_preview.status_code == 200
    assert advisor_preview.json()["data"]["approved_decisions"] == approved
    assert _get(client, "james", "/evidence/decision-liquidity-reserve").status_code == 200

    _consent(client, "robert", RESERVE, "decision_excerpt", JAMES, active=False)
    assert _get(client, "robert", "/heir-preview").json()["data"]["approved_decisions"] == []
    assert _snapshot(client, "james")["approved_decisions"] == []
    assert _get(client, "james", "/evidence/decision-liquidity-reserve").status_code == 404


def test_consent_change_invalidates_goal_derived_insights(client: TestClient, db_session: Session):
    family = db_session.get(Family, MORGAN)
    scope = {"organization_id": family.organization_id, "family_id": family.id}

    def insight(key: str, payload: dict) -> Insight:
        row = Insight(insight_key=key, type="liquidity_gap", title=key, payload=payload, consent_revision=0, **scope)
        db_session.add(row)
        db_session.flush()
        return row

    def action(row: Insight, status: str) -> AdvisorAction:
        a = AdvisorAction(
            insight_id=row.id,
            advisor_person_id=SARAH,
            action_type="parent_review",
            draft_text=f"draft {status}",
            status=status,
            **scope,
        )
        db_session.add(a)
        return a

    goal_insight = insight("goal-derived", {"goal_ref": "goal-james-business", "headline": 0.4})
    other = insight("estate-only", {"evidence": []})
    goal_actions = {status: action(goal_insight, status) for status in ("draft", "approved", "completed")}
    other_action = action(other, "draft")
    db_session.commit()
    ids = {"goal": goal_insight.id, "other": other.id}
    action_ids = {status: a.id for status, a in goal_actions.items()}
    other_action_id = other_action.id

    _share_goal(client, "goal_summary")
    db_session.expire_all()

    invalidated = db_session.get(Insight, ids["goal"])
    assert invalidated.review_status == "invalidated"
    assert invalidated.payload == {"withdrawn": "consent_revoked"}
    for status in ("draft", "approved"):
        cancelled = db_session.get(AdvisorAction, action_ids[status])
        assert (cancelled.status, cancelled.draft_text) == ("cancelled", "")
    completed = db_session.get(AdvisorAction, action_ids["completed"])
    assert (completed.status, completed.draft_text) == ("completed", "draft completed")

    # The consent handler leaves a non-goal-derived insight alone (payload and draft kept). The readiness
    # pipeline that runs after it then retires the row, because no current record produces it.
    kept = db_session.get(Insight, ids["other"])
    assert kept.review_status == "invalidated"
    assert kept.payload == {"evidence": []}
    assert db_session.get(AdvisorAction, other_action_id).status == "draft"
    assert db_session.scalar(select(Family.consent_revision).where(Family.id == MORGAN)) == 1
