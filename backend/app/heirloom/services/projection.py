"""Per-audience reads: what one actor may see, re-checked against SQL on every read.

`Visibility` is the policy; `authorized_graph_projection` applies it to the stored graph. The stored
graph is advisor-level, so nothing reaches a browser without passing through here (or through the
audience's own snapshot DTO).
"""

from datetime import date
from functools import cached_property
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.heirloom.context.access import FamilyActor
from app.heirloom.dto.advisor import AdvisorGoalDetail, AdvisorGoalSummary
from app.heirloom.dto.common import GraphDTO
from app.heirloom.dto.heir import HeirDecisionView
from app.heirloom.graph.factory import get_graph_repo
from app.heirloom.graph.repository import GEdge, GNode
from app.heirloom.models import (
    Asset,
    DecisionRecord,
    FamilyPerson,
    ForecastScenario,
    HeirGoal,
    Insight,
    LegalInstrument,
    TransferIntent,
)
from app.heirloom.services import consent
from app.heirloom.services import graph as graph_service

EVIDENCE_KINDS = frozenset({"asset", "instrument", "intent", "decision", "goal"})
_KIND_MODEL = {
    "person": FamilyPerson,
    "asset": Asset,
    "restriction": Asset,
    "instrument": LegalInstrument,
    "intent": TransferIntent,
    "decision": DecisionRecord,
    "goal": HeirGoal,
    "forecast": ForecastScenario,
    "insight": Insight,
}
_PARENT_EDGES = frozenset(
    {"OWNS", "DOCUMENTS", "REFERS_TO", "INTENDED_FOR", "CONCERNS", "REVIEWED_BY", "HAS_RESTRICTION"}
)
_HEIR_EDGES = frozenset({"STATED", "REVIEWED_BY"})


class Visibility:
    """One actor's read permissions inside their family. Role comes from `FamilyActor` (the DB)."""

    def __init__(self, actor: FamilyActor, session: Session):
        self.session = session
        self.family = actor.family
        self.me = actor.person
        self.role = actor.role

    @property
    def is_advisor(self) -> bool:
        return self.role == "advisor"

    @cached_property
    def _own_asset_ids(self) -> frozenset[UUID]:
        if self.role != "parent":
            return frozenset()
        return frozenset(
            self.session.scalars(
                select(Asset.id).where(Asset.family_id == self.family.id, Asset.owner_person_id == self.me.id)
            )
        )

    @cached_property
    def heir_decisions(self) -> dict[str, HeirDecisionView]:
        """Decisions the parent approved for this heir, by decision id (empty for other roles)."""
        if self.role != "adult_heir":
            return {}
        from app.heirloom.services import snapshots  # snapshots imports this module

        return {v.decision_id: v for v in snapshots.heir_approved_decisions(self.session, self.family, self.me)}

    def asset(self, asset: Asset) -> bool:
        return self.is_advisor or asset.id in self._own_asset_ids

    def intent(self, intent: TransferIntent) -> bool:
        return self.is_advisor or intent.asset_id in self._own_asset_ids

    def instrument(self, instrument: LegalInstrument) -> bool:
        if self.is_advisor:
            return True
        if self.role != "parent":
            return False
        asset_ids = self.session.scalars(
            select(TransferIntent.asset_id).where(TransferIntent.instrument_id == instrument.id)
        )
        return any(asset_id in self._own_asset_ids for asset_id in asset_ids)

    def decision(self, decision: DecisionRecord) -> bool:
        if self.role == "adult_heir":
            return str(decision.id) in self.heir_decisions
        return self.is_advisor or (self.role == "parent" and decision.person_id == self.me.id)

    def advisor_goal(self, goal: HeirGoal) -> AdvisorGoalSummary | AdvisorGoalDetail | None:
        if not self.is_advisor or goal.family_id != self.family.id:
            return None
        return consent.goal_view_for_advisor(self.session, self.family, goal)

    def own_goal(self, goal: HeirGoal) -> bool:
        return self.role == "adult_heir" and goal.heir_person_id == self.me.id

    def _goal_shared(self, goal: HeirGoal | None) -> bool:
        return goal is not None and self.advisor_goal(goal) is not None

    def forecast(self, scenario: ForecastScenario) -> bool:
        if not self.is_advisor:
            return False
        return scenario.goal_id is None or self._goal_shared(self.session.get(HeirGoal, scenario.goal_id))

    def insight(self, insight: Insight) -> bool:
        if not self.is_advisor or insight.review_status == "invalidated":
            return False
        goal_ref = (insight.payload or {}).get("goal_ref")
        if goal_ref is None:
            return True
        goal = graph_service.find_record(self.session, self.family, goal_ref, (HeirGoal,))
        return self._goal_shared(goal)


def _authorize(node: GNode, row, vis: Visibility) -> GNode | None:
    """The node as this actor may see it, or None. `row` is the SQL record behind the node."""
    if row is None:
        return None  # stale graph: the SQL record is gone
    match node.kind:
        case "person":
            return node
        case "asset":
            return node if vis.asset(row) else None
        case "restriction":
            return node if vis.asset(row) and graph_service.has_restriction(row) else None
        case "instrument":
            return node if vis.instrument(row) else None
        case "intent":
            return node if vis.intent(row) else None
        case "decision":
            if not vis.decision(row):
                return None
            if vis.role != "adult_heir":
                return node
            view = vis.heir_decisions[str(row.id)]
            return node.model_copy(
                update={
                    "label": view.title,
                    "classification": "authorized_heir_history",
                    "props": {"date": view.date.isoformat()},
                }
            )
        case "goal":
            if vis.own_goal(row):
                return node
            view = vis.advisor_goal(row)
            if view is None:
                return None
            return node.model_copy(
                update={"classification": "advisor_approved_goal", "props": view.model_dump(mode="json")}
            )
        case "forecast":
            return node if vis.forecast(row) else None
        case "insight":
            return node if vis.insight(row) else None
    return None


def _authorize_edge(edge: GEdge, role: str) -> GEdge | None:
    if role == "advisor":
        if edge.type == "STATED":
            return edge.model_copy(update={"classification": "advisor_approved_goal"})
        return edge
    if role == "parent":
        return edge if edge.type in _PARENT_EDGES else None
    if edge.type not in _HEIR_EDGES:
        return None
    if edge.type == "REVIEWED_BY":
        return edge.model_copy(update={"classification": "authorized_heir_history"})
    return edge


def authorized_graph_projection(actor: FamilyActor, session: Session, as_of: date | None) -> GraphDTO:
    family = actor.family
    repo, _degraded = get_graph_repo()
    if not repo.read_family(family.organization_id, family.id, None)[0]:
        graph_service.rebuild_family_graph(session, family)  # e.g. a restart with a persistent database
    nodes, edges = repo.read_family(family.organization_id, family.id, as_of)

    rows = graph_service.family_records(session, family)
    vis = Visibility(actor, session)
    kept: dict[str, GNode] = {}
    for node in nodes:
        key = node.props.get("asset_ref") if node.kind == "restriction" else node.record_id
        authorized = _authorize(node, rows.get((_KIND_MODEL[node.kind], key)), vis)
        if authorized is not None:
            kept[node.record_id] = authorized

    kept_edges = []
    for edge in edges:
        if edge.source_id in kept and edge.target_id in kept:
            authorized_edge = _authorize_edge(edge, actor.role)
            if authorized_edge is not None:
                kept_edges.append(authorized_edge)

    return GraphDTO(
        nodes=list(kept.values()),
        edges=kept_edges,
        evidence_refs=sorted(ref for ref, n in kept.items() if n.kind in EVIDENCE_KINDS),
        revision=family.data_revision,
    )
