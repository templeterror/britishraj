from conftest import auth
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.heirloom.ids import ref_id
from app.heirloom.models import Family, ForecastScenario, Insight
from app.heirloom.services import readiness
from app.heirloom.services.seed import load_fixture

MORGAN = ref_id("demo-morgan")
BASE = f"/api/v1/families/{MORGAN}"
GOAL = ref_id("goal-james-business")
SARAH = ref_id("person-sarah")
INSUFFICIENT = "Insufficient modeling data: goal timing or amount not shared"


def _share_goal(client: TestClient, active: bool = True) -> None:
    response = client.put(
        f"{BASE}/consents/{GOAL}",
        headers=auth(client, "james"),
        json={"scope": "goal_summary", "recipient_person_id": str(SARAH), "active": active},
    )
    assert response.status_code == 200, response.text


def _patch_goal(client: TestClient, version: int, **fields) -> None:
    response = client.patch(
        f"{BASE}/heir-goals/{GOAL}", headers=auth(client, "james"), json={"version": version, **fields}
    )
    assert response.status_code == 200, response.text


def _insights(client: TestClient, persona: str = "sarah", **params) -> list[dict]:
    response = client.get(f"{BASE}/insights", headers=auth(client, persona), params=params)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()["data"]


def _one(client: TestClient, type_: str) -> dict:
    (insight,) = _insights(client)
    assert insight["type"] == type_, insight
    return insight


def _kinds(insight: dict) -> set[str]:
    return {e["kind"] for e in insight["evidence"]}


def _forecast(client: TestClient, scenario_id: str, persona: str = "sarah"):
    return client.get(f"{BASE}/forecasts/{scenario_id}", headers=auth(client, persona))


def _graph(client: TestClient, persona: str) -> dict:
    response = client.get(f"{BASE}/graph", headers=auth(client, persona))
    assert response.status_code == 200, response.text
    return response.json()["data"]


def test_no_flag_until_james_shares(client: TestClient):
    assert _insights(client) == []

    _share_goal(client)
    insight = _one(client, "liquidity_gap")
    assert {"estate_instrument", "estate_intent", "asset", "goal", "forecast"} <= _kinds(insight)
    assert "decision" not in _kinds(insight)  # decision-retain-llc is still a candidate
    assert insight["goal_ref"] == "goal-james-business"
    assert insight["review_status"] == "new"
    assert insight["consent_revision"] == 1
    assert insight["headline_probability"] <= 0.15
    assert "24 months" in insight["headline_condition"]
    assert len(insight["scenario_rows"]) == 12
    assert all(row["scenario_id"] for row in insight["scenario_rows"])

    verified = client.post(
        f"{BASE}/decisions/decision-retain-llc/verify",
        headers=auth(client, "sarah"),
        json={"approved": True, "edited_rationale": None, "note": None},
    )
    assert verified.status_code == 200, verified.text
    insight = _one(client, "liquidity_gap")
    assert {"estate_instrument", "estate_intent", "asset", "decision", "goal", "forecast"} <= _kinds(insight)
    (decision,) = [e for e in insight["evidence"] if e["kind"] == "decision"]
    assert decision["ref"] == "decision-retain-llc"


def test_goal_year_3_flips_to_timing(client: TestClient):
    _share_goal(client)
    _one(client, "liquidity_gap")

    _patch_goal(client, 1, target_year=2029, horizon_min_years=2, horizon_max_years=3)
    insights = _insights(client)
    assert {i["type"] for i in insights} == {"timing_gap", "timing_review"}
    assert all(i["headline_probability"] is None for i in insights)


def test_foundation_goal_recomputes(client: TestClient):
    _share_goal(client)
    _one(client, "liquidity_gap")

    foundation = load_fixture("morgan_family.json")["goal_presets"]["foundation"]
    _patch_goal(client, 1, **foundation)
    insight = _one(client, "relationship_opportunity")
    assert "No modeled mismatch under these assumptions" in insight["known"]
    assert insight["filter_tags"] == ["heir_conversation"]


def test_goal_without_amount_is_insufficient_data(client: TestClient):
    _share_goal(client)
    _patch_goal(client, 1, amount_target=None)
    insight = _one(client, "relationship_opportunity")
    assert insight["headline_probability"] is None
    assert insight["headline_condition"] == INSUFFICIENT
    assert insight["scenario_rows"] == []


def test_revocation_removes_insight_and_forecast(client: TestClient):
    _share_goal(client)
    insight = _one(client, "liquidity_gap")
    row = next(
        r for r in insight["scenario_rows"] if (r["transfer_year"], r["preset"]) == (10, "exit_delay_24m")
    )

    response = _forecast(client, row["scenario_id"])
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    forecast = response.json()["data"]
    assert forecast["p_cash_covers_goal"] == row["p"]
    assert forecast["settings"]["transfer_year"] == 10
    assert forecast["settings"]["preset"] == "exit_delay_24m"
    assert forecast["settings"]["goal_year"] == 12
    assert forecast["seed"] == 40626
    assert forecast["model_version"] == "relay-forecast-1.0"
    assert len(forecast["input_hash"]) == 64
    assert len(forecast["cash_by_year"]) == 31
    assert forecast["computed_at"]

    _share_goal(client, active=False)
    assert _insights(client) == []
    assert _forecast(client, row["scenario_id"]).status_code == 404
    graph = _graph(client, "sarah")
    assert not {"goal", "forecast", "insight"} & {n["kind"] for n in graph["nodes"]}
    assert "goal-james-business" not in str(graph)


def test_superseding_letter_invalidates_asset_alert(client: TestClient):
    _share_goal(client)
    _one(client, "liquidity_gap")

    response = client.post(
        f"{BASE}/instruments/instr-estate-letter-2026/status",
        headers=auth(client, "sarah"),
        json={"status": "superseded"},
    )
    assert response.status_code == 200, response.text
    insight = _one(client, "relationship_opportunity")
    assert _kinds(insight) == {"goal"}
    assert insight["scenario_rows"] == []
    for word in ("llc", "intend", "estate", "inherit"):
        assert word not in insight["summary"].lower()


def test_conflicting_amendment_yields_legal_review(client: TestClient):
    _share_goal(client)
    imported = client.post(
        f"{BASE}/estate-intents/import",
        headers=auth(client, "sarah"),
        json={"fixture_ref": "conflicting_amendment"},
    )
    assert imported.status_code == 200, imported.text
    _one(client, "liquidity_gap")  # an unverified amendment changes nothing

    (amendment,) = imported.json()["data"]
    verified = client.post(
        f"{BASE}/estate-intents/{amendment['id']}/verify",
        headers=auth(client, "sarah"),
        json={"verified": True, "notes": "Checked.", "source_version": 1},
    )
    assert verified.status_code == 200, verified.text
    insight = _one(client, "legal_review")
    assert insight["filter_tags"] == ["legal_source_conflict"]
    assert insight["headline_probability"] is None


def test_heir_insights_403(client: TestClient):
    _share_goal(client)
    insight = _one(client, "liquidity_gap")
    scenario_id = insight["scenario_rows"][0]["scenario_id"]
    for persona in ("james", "robert"):
        headers = auth(client, persona)
        assert client.get(f"{BASE}/insights", headers=headers).status_code == 403, persona
        assert _forecast(client, scenario_id, persona).status_code == 403, persona
        review = client.post(
            f"{BASE}/insights/{insight['id']}/review", headers=headers, json={"review_status": "reviewed"}
        )
        assert review.status_code == 403, persona


def test_forecast_and_insight_nodes_advisor_only(client: TestClient):
    _share_goal(client)
    insight = _one(client, "liquidity_gap")
    scenario_ids = {r["scenario_id"] for r in insight["scenario_rows"]}

    graph = _graph(client, "sarah")
    nodes = {n["record_id"]: n for n in graph["nodes"]}
    forecasts = {ref for ref, n in nodes.items() if n["kind"] == "forecast"}
    assert forecasts == {f"forecast-{sid}" for sid in scenario_ids}
    (insight_ref,) = [ref for ref, n in nodes.items() if n["kind"] == "insight"]
    supported = {
        e["target_id"]
        for e in graph["edges"]
        if e["type"] == "SUPPORTED_BY" and e["source_id"] == insight_ref
    }
    assert {"intent-james-llc", "asset-family-llc", "goal-james-business"} | forecasts <= supported
    tests_edges = {(e["source_id"], e["target_id"]) for e in graph["edges"] if e["type"] == "TESTS"}
    assert tests_edges == {(ref, "goal-james-business") for ref in forecasts}

    for persona in ("robert", "james"):
        kinds = {n["kind"] for n in _graph(client, persona)["nodes"]}
        assert not {"forecast", "insight"} & kinds, persona


def test_review_status_persists_across_identical_recompute(client: TestClient, db_session: Session):
    _share_goal(client)
    insight = _one(client, "liquidity_gap")
    response = client.post(
        f"{BASE}/insights/{insight['id']}/review",
        headers=auth(client, "sarah"),
        json={"review_status": "reviewed"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["data"]["review_status"] == "reviewed"
    assert [i["id"] for i in _insights(client, status="reviewed")] == [insight["id"]]
    assert _insights(client, status="new") == []
    assert [i["id"] for i in _insights(client, tag="needs_parent_review")] == [insight["id"]]
    assert _insights(client, tag="heir_conversation") == []
    bad = client.get(f"{BASE}/insights", headers=auth(client, "sarah"), params={"tag": "nope"})
    assert bad.status_code == 422

    _patch_goal(client, 1, milestone="Hire a cofounder")  # not shared under a summary grant
    after = _one(client, "liquidity_gap")
    assert after["id"] == insight["id"]
    assert after["review_status"] == "reviewed"

    scenarios = set(
        db_session.scalars(select(ForecastScenario.id).where(ForecastScenario.family_id == MORGAN))
    )
    result = readiness.recompute(db_session, db_session.get(Family, MORGAN))
    assert result == readiness.RecomputeResult(created=0, kept=1, invalidated=0)
    assert (
        set(db_session.scalars(select(ForecastScenario.id).where(ForecastScenario.family_id == MORGAN)))
        == scenarios
    )
    statuses = db_session.scalars(select(Insight.review_status).where(Insight.family_id == MORGAN)).all()
    assert statuses == ["reviewed"]
