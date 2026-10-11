"""In-process graph store: the default, and the fallback when Neo4j is unreachable."""

import threading
from datetime import date
from uuid import UUID

from app.heirloom.graph.repository import GEdge, GNode, at_as_of


class InMemoryGraphRepository:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._nodes: dict[tuple[str, UUID], dict[str, GNode]] = {}
        self._edges: dict[tuple[str, UUID], dict[tuple[str, str, str], GEdge]] = {}

    def upsert_nodes(self, org: str, family_id: UUID, nodes: list[GNode]) -> None:
        with self._lock:
            store = self._nodes.setdefault((org, family_id), {})
            store.update({n.record_id: n for n in nodes})

    def upsert_edges(self, org: str, family_id: UUID, edges: list[GEdge]) -> None:
        with self._lock:
            store = self._edges.setdefault((org, family_id), {})
            store.update({e.key: e for e in edges})

    def replace_family(self, org: str, family_id: UUID, nodes: list[GNode], edges: list[GEdge]) -> None:
        with self._lock:
            self._nodes[(org, family_id)] = {n.record_id: n for n in nodes}
            self._edges[(org, family_id)] = {e.key: e for e in edges}

    def read_family(
        self, org: str, family_id: UUID, as_of: date | None
    ) -> tuple[list[GNode], list[GEdge]]:
        with self._lock:
            nodes = list(self._nodes.get((org, family_id), {}).values())
            edges = list(self._edges.get((org, family_id), {}).values())
        return at_as_of(nodes, edges, as_of)
