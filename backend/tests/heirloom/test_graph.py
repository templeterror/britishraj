from conftest import auth
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.heirloom.dto.advisor import AdvisorGoalSummary
from app.heirloom.dto.heir import HeirDecisionView
from app.heirloom.graph.factory import get_graph_repo
from app.heirloom.ids import ref_id
from app.heirloom.models import AuditLog, DecisionRecord, Family
from app.heirloom.services import consent, events, snapshots
from app.heirloom.services import graph as graph_service

MORGAN = ref_id("demo-morgan")
ORG = "org_relay_demo"


def _graph(client: TestClient, persona: str, as_of: str | None = None) -> dict:
    params = {"as_of": as_of} if as_of else None
    response = client.get(f"/api/v1/families/{MORGAN}/graph", headers=auth(client, persona), params=params)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()["data"]


def _nodes(graph: dict) -> dict[str, dict]:
    return {n["record_id"]: n for n in graph["nodes"]}


def _edges(graph: dict, type_: str) -> list[tuple[str, str]]:
    return [(e["source_id"], e["target_id"]) for e in graph["edges"] if e["type"] == type_]


def _evidence(client: TestClient, persona: str, ref: str):
    return client.get(f"/api/v1/families/{MORGAN}/evidence/{ref}", headers=auth(client, persona))


def test_intended_for_only_for_verified_current_intent(client: TestClient):
    graph = _graph(client, "sarah")
    assert _edges(graph, "INTENDED_FOR") == [("intent-james-llc", "person-james")]

    old = _nodes(graph)["intent-2024-llc-split"]
    assert old["valid_to"] == "2026-03-02"
    assert old["evidence_status"] == "superseded"
    assert not [e for e in graph["edges"] if e["type"] == "INTENDED_FOR" and e["source_id"] == old["record_id"]]


def test_candidate_decision_not_in_graph_as_verified(client: TestClient):
    nodes = _nodes(_graph(client, "sarah"))
    assert nodes["decision-retain-llc"]["evidence_status"] == "candidate"
    assert nodes["decision-liquidity-reserve"]["evidence_status"] == "verified"


def test_heir_graph_excludes_private_parent_nodes(client: TestClient):
    graph = _graph(client, "james")
    nodes = _nodes(graph)
    assert not [n for n in graph["nodes"] if n["classification"] == "internal_parent_advisor"]
    assert {n["kind"] for n in graph["nodes"]} == {"person", "goal"}
    assert nodes["goal-james-business"]["classification"] == "private_heir"
    assert _edges(graph, "STATED") == [("person-james", "goal-james-business")]
    assert "LLC" not in str(graph)
    node_ids = set(nodes)
    assert all(e["source_id"] in node_ids and e["target_id"] in node_ids for e in graph["edges"])


def test_as_of_before_2026_shows_2024_intent_current(client: TestClient):
    graph = _graph(client, "sarah", as_of="2025-01-01")
    nodes = _nodes(graph)
    assert "intent-james-llc" not in nodes
    assert nodes["intent-2024-llc-split"]["valid_to"] is None
    assert "decision-retain-llc" not in nodes  # dated 2026-04-15
    assert _edges(graph, "INTENDED_FOR") == []


def test_rebuild_is_deterministic(client: TestClient, db_session: Session):
    family = db_session.get(Family, MORGAN)
    repo, _ = get_graph_repo()

    graph_service.rebuild_family_graph(db_session, family)
    first = repo.read_family(ORG, MORGAN, None)
    graph_service.rebuild_family_graph(db_session, family)
    second = repo.read_family(ORG, MORGAN, None)

    assert first == second
    nodes, edges = first
    assert [n.record_id for n in nodes] == sorted(n.record_id for n in nodes)
    assert [(e.type, e.source_id, e.target_id) for e in edges] == sorted(
        (e.type, e.source_id, e.target_id) for e in edges
    )


def test_evidence_returns_transcript_excerpt_for_advisor(client: TestClient, db_session: Session):
    response = _evidence(client, "sarah", "decision-retain-llc")
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    data = response.json()["data"]
    assert "keep control of the business" in data["excerpt"]
    assert data["kind"] == "decision"
    assert data["status"] == "candidate"
    assert data["document_title"] == "Meeting transcript, Robert Morgan and Sarah Lin, 2026-04-15"
    assert data["document_date"] == "2026-04-15"
    assert data["locator"]["start_seconds"] == 113
    row = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "evidence.read", AuditLog.actor_external_id == "demo_sarah")
    ).one()
    assert row.allowed is True


def test_evidence_returns_dated_letter_for_verified_intent(client: TestClient):
    data = _evidence(client, "sarah", "intent-james-llc").json()["data"]
    assert data["kind"] == "estate_intent"
    assert data["status"] == "verified"
    assert data["document_date"] == "2026-03-02"
    assert "not a transfer of ownership" in data["excerpt"]
    assert "revocable" in data["qualifier"].lower()


def test_evidence_404_for_heir_on_intent(client: TestClient, db_session: Session):
    response = _evidence(client, "james", "intent-james-llc")
    assert response.status_code == 404
    assert response.json()["errors"][0]["code"] == "not_found"
    assert response.json()["data"] is None
    unknown = _evidence(client, "james", "intent-does-not-exist")
    assert unknown.status_code == 404
    assert unknown.json()["errors"] == response.json()["errors"]  # no existence leak
    denied = db_session.scalars(
        select(AuditLog).where(AuditLog.action == "evidence.read", AuditLog.allowed.is_(False))
    ).all()
    assert len(denied) == 2


def test_evidence_404_for_advisor_on_unshared_goal(client: TestClient):
    assert _evidence(client, "sarah", "goal-james-business").status_code == 404
    assert _evidence(client, "robert", "goal-james-business").status_code == 404
    own = _evidence(client, "james", "goal-james-business")
    assert own.status_code == 200
    assert "software company" in own.json()["data"]["excerpt"]


def test_advisor_graph_hides_unshared_goal_and_shows_restriction(client: TestClient):
    graph = _graph(client, "sarah")
    nodes = _nodes(graph)
    assert not [n for n in graph["nodes"] if n["kind"] == "goal"]
    assert nodes["restriction-asset-family-llc"]["kind"] == "restriction"
    assert _edges(graph, "HAS_RESTRICTION") == [("asset-family-llc", "restriction-asset-family-llc")]
    assert ("person-james", "asset-family-llc") not in _edges(graph, "OWNS")
    assert not [e for e in _edges(graph, "OWNS") if e[0] == "person-james"]
    assert {"intent-james-llc", "decision-retain-llc", "asset-family-llc"} <= set(graph["evidence_refs"])


def test_parent_graph_excludes_goal_and_advisor_only_nodes(client: TestClient):
    graph = _graph(client, "robert")
    classes = {n["classification"] for n in graph["nodes"]}
    assert not classes & {"private_heir", "advisor_approved_goal", "advisor_only"}
    assert "goal-james-business" not in _nodes(graph)
    assert _edges(graph, "INTENDED_FOR") == [("intent-james-llc", "person-james")]


def test_shared_goal_appears_for_advisor_through_consent_gate(client: TestClient, monkeypatch):
    summary = AdvisorGoalSummary(
        goal_id=str(ref_id("goal-james-business")),
        kind="business",
        horizon_band="8–12 years",
        amount_band="about $500K",
        amount_band_mid=500000,
        horizon_max_years=12,
    )
    monkeypatch.setattr(consent, "goal_view_for_advisor", lambda _s, _f, _g: summary)

    graph = _graph(client, "sarah")
    goal = _nodes(graph)["goal-james-business"]
    assert goal["classification"] == "advisor_approved_goal"
    assert goal["props"] == summary.model_dump(mode="json")
    assert "software company" not in str(graph)
    evidence = _evidence(client, "sarah", "goal-james-business")
    assert evidence.status_code == 200
    assert "software company" not in evidence.text


def test_heir_sees_only_approved_decision_nodes(client: TestClient, monkeypatch):
    view = HeirDecisionView(
        decision_id=str(ref_id("decision-liquidity-reserve")),
        date="2023-11-09",
        title="Build a two-year liquidity reserve",
        rationale=None,
        source_title=None,
        locator=None,
        verified_by_display="Sarah Lin",
        asset_kind="cash",
    )
    monkeypatch.setattr(snapshots, "heir_approved_decisions", lambda _s, _f, _p: [view])

    graph = _graph(client, "james")
    decisions = [n for n in graph["nodes"] if n["kind"] == "decision"]
    assert [d["record_id"] for d in decisions] == ["decision-liquidity-reserve"]
    assert decisions[0]["classification"] == "authorized_heir_history"
    assert not [n for n in graph["nodes"] if n["classification"] == "internal_parent_advisor"]
    assert _evidence(client, "james", "decision-liquidity-reserve").status_code == 200
    assert _evidence(client, "james", "decision-retain-llc").status_code == 404


def test_domain_event_rebuilds_graph(client: TestClient, db_session: Session):
    decision = db_session.get(DecisionRecord, ref_id("decision-retain-llc"))
    decision.verification_status = "verified"
    events.emit(db_session, db_session.get(Family, MORGAN), "decision.verified.v1", "decision-retain-llc", {})
    db_session.commit()

    graph = _graph(client, "sarah")
    assert _nodes(graph)["decision-retain-llc"]["evidence_status"] == "verified"
    assert graph["revision"] == 1
