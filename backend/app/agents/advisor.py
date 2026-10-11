"""Code decides whether the wealth manager needs to look. The advisor agent writes the alert.

The route is a fixed rule over the tree, so what reaches the manager's
inbox is predictable. The advisor model sees only the tree and the
analyst's findings, never the raw facts or evidence, and only runs when
the route is review or urgent.
"""

from __future__ import annotations

import json

from app.agents.catalog import TaskModels
from app.agents.client import ChatClient, json_schema
from app.agents.intake import record
from app.agents.schemas import AdvisorAlert, AdvisorText, CallRecord, DecisionTree, Node, Route

ADVISOR_INSTRUCTIONS = (
    "You write to the family's wealth manager about one heir's goal. "
    "tree is the full check with outcomes, figures, and the analyst's findings. route says why it reached you. "
    "headline is one line, at most fifteen words, naming the mismatch. "
    "why is at most three sentences on what the tree shows and why it matters before the family meets. "
    "next_actions is one to three items, each naming who the manager should talk to (the parent, the heir, "
    "or both) and the question to ask them. "
    "Use only numbers that appear in the tree. Never propose buying, selling, or moving money."
)


def route(tree: DecisionTree) -> tuple[Route, str, list[str]]:
    parents = parent_map(tree.root)
    highs = [node for node in tree.nodes() if node.outcome == "misaligned" and node.severity == "high"]
    mediums = [node for node in tree.nodes() if node.outcome == "misaligned" and node.severity == "medium"]
    if highs:
        names = ", ".join(node.id for node in highs)
        return "urgent", f"A high-severity mismatch: {names}.", path_to(highs, parents)
    if tree.root.outcome == "gap":
        return "review", "The heir could not make the goal specific after three questions.", [tree.root.id]
    if mediums:
        names = ", ".join(node.id for node in mediums)
        return "review", f"A medium-severity mismatch: {names}.", path_to(mediums, parents)
    return "none", "Every check is aligned or only missing evidence.", []


def parent_map(root: Node) -> dict[str, str | None]:
    parents: dict[str, str | None] = {root.id: None}
    for node in root.walk():
        for child in node.children:
            parents[child.id] = node.id
    return parents


def path_to(nodes: list[Node], parents: dict[str, str | None]) -> list[str]:
    path: list[str] = []
    for node in nodes:
        chain: list[str] = []
        current: str | None = node.id
        while current is not None:
            chain.append(current)
            current = parents.get(current)
        for item in reversed(chain):
            if item not in path:
                path.append(item)
    return path


def tree_packet(tree: DecisionTree) -> dict:
    return {
        "score": tree.score,
        "rubric": tree.rubric,
        "verdict": tree.verdict,
        "nodes": [
            {
                "id": node.id,
                "title": node.title,
                "outcome": node.outcome,
                "severity": node.severity,
                "detail": node.detail,
                "finding": node.finding,
            }
            for node in tree.nodes()
            if node.outcome != "skipped"
        ],
        "meeting_agenda": tree.meeting_agenda,
    }


def write_alert(
    client: ChatClient,
    tasks: TaskModels,
    tree: DecisionTree,
    calls: list[CallRecord],
) -> AdvisorAlert:
    chosen, reason, path = route(tree)
    alert = AdvisorAlert(route=chosen, reason=reason, path=path, agenda=list(tree.meeting_agenda))
    if chosen == "none":
        return alert
    payload = {"route": chosen, "reason": reason, "path": path, "tree": tree_packet(tree)}
    completion = client.complete(
        task="advisor",
        model=tasks.advisor_model,
        effort=tasks.advisor_effort,
        messages=[
            {"role": "system", "content": ADVISOR_INSTRUCTIONS},
            {"role": "user", "content": json.dumps(payload)},
        ],
        schema_name="advisor_text",
        schema=json_schema(AdvisorText),
    )
    calls.append(record("advisor", completion))
    text = AdvisorText.model_validate_json(completion.text)
    return alert.model_copy(
        update={"headline": text.headline, "why": text.why, "next_actions": list(text.next_actions)}
    )
