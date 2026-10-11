"""The family knowledge graph's storage contract.

Graph stores hold the full, advisor-level graph for a family. They are never read by a browser
directly: `services.projection` filters every read per audience against SQL first.
"""

from datetime import date
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

NodeKind = Literal[
    "person", "asset", "instrument", "intent", "decision", "goal", "forecast", "insight", "restriction"
]
Classification = Literal[
    "internal_parent_advisor",
    "private_heir",
    "advisor_approved_goal",
    "authorized_heir_history",
    "family_member",
    "advisor_only",
]
EvidenceStatus = Literal["verified", "candidate", "superseded", "contested", "unknown"]
EdgeType = Literal[
    "OWNS",
    "DOCUMENTS",
    "REFERS_TO",
    "INTENDED_FOR",
    "CONCERNS",
    "REVIEWED_BY",
    "STATED",
    "HAS_RESTRICTION",
    "MODELS",
    "TESTS",
    "SUPPORTED_BY",
]


class GNode(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    record_id: str
    label: str
    kind: NodeKind
    classification: Classification
    valid_from: date | None = None
    valid_to: date | None = None
    evidence_status: EvidenceStatus
    props: dict = Field(default_factory=dict)


class GEdge(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    type: EdgeType
    source_id: str
    target_id: str
    valid_from: date | None = None
    valid_to: date | None = None
    classification: Classification

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.type, self.source_id, self.target_id)


class GraphRepository(Protocol):
    def upsert_nodes(self, org: str, family_id: UUID, nodes: list[GNode]) -> None: ...

    def upsert_edges(self, org: str, family_id: UUID, edges: list[GEdge]) -> None: ...

    def replace_family(self, org: str, family_id: UUID, nodes: list[GNode], edges: list[GEdge]) -> None: ...

    def read_family(
        self, org: str, family_id: UUID, as_of: date | None
    ) -> tuple[list[GNode], list[GEdge]]: ...


def _at(valid_from: date | None, valid_to: date | None, as_of: date) -> tuple[bool, date | None]:
    """Whether a record existed on `as_of`, and its `valid_to` as seen from that date."""
    if valid_from is not None and valid_from > as_of:
        return False, None
    return True, valid_to if valid_to is not None and valid_to <= as_of else None


def at_as_of(
    nodes: list[GNode], edges: list[GEdge], as_of: date | None
) -> tuple[list[GNode], list[GEdge]]:
    """The graph as it stood on `as_of`, sorted.

    Records that did not exist yet are dropped; an end date after `as_of` had not happened yet, so it
    reads as open (`valid_to=None`). Edges lose their endpoints' absence too.
    """
    nodes = sorted(nodes, key=lambda n: n.record_id)
    edges = sorted(edges, key=lambda e: e.key)
    if as_of is None:
        return nodes, edges

    kept_nodes = []
    for node in nodes:
        exists, valid_to = _at(node.valid_from, node.valid_to, as_of)
        if exists:
            kept_nodes.append(node if valid_to == node.valid_to else node.model_copy(update={"valid_to": None}))
    ids = {n.record_id for n in kept_nodes}
    kept_edges = []
    for edge in edges:
        exists, valid_to = _at(edge.valid_from, edge.valid_to, as_of)
        if exists and edge.source_id in ids and edge.target_id in ids:
            kept_edges.append(edge if valid_to == edge.valid_to else edge.model_copy(update={"valid_to": None}))
    return kept_nodes, kept_edges
