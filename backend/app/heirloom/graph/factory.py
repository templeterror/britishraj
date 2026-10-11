"""The single place that picks the graph store. Task 10 adds Neo4j selection and degraded fallback."""

from app.heirloom.graph.memory import InMemoryGraphRepository
from app.heirloom.graph.repository import GraphRepository

_memory_repo = InMemoryGraphRepository()


def get_graph_repo() -> tuple[GraphRepository, list[str]]:
    """The graph store and the degraded features to report in `meta.degraded` (none for memory)."""
    return _memory_repo, []
