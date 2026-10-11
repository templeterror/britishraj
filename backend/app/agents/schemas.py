"""Contracts between the three agents and the code that routes between them.

Intake reads words and returns a GoalBrief. Checks turn the brief, the
liquidity facts, and the evidence into a DecisionTree whose outcomes are
computed in code. The analyst explains each node. Code picks the route.
The advisor writes the alert the wealth manager acts on.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


SliceName = Literal["quotes", "home", "comps", "funding"]
Purpose = Literal["company", "home", "education", "family", "other"]
Missing = Literal["amount", "horizon", "purpose"]
Severity = Literal["low", "medium", "high"]
Outcome = Literal["aligned", "misaligned", "gap", "skipped", "pending"]
Route = Literal["none", "review", "urgent"]
Status = Literal["asking", "ready", "ready_with_gaps"]


class GoalBrief(BaseModel):
    intent: str
    amount_usd: float | None = None
    amount_is_estimate: bool = False
    horizon_months: int | None = None
    purpose: Purpose | None = None
    must_be_reachable: bool = False
    exclusions: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    slices: list[SliceName] = Field(default_factory=list)
    missing: list[Missing] = Field(default_factory=list)


class IntakeTurn(BaseModel):
    brief: GoalBrief
    question: str | None = None


class Message(BaseModel):
    role: Literal["heir", "agent"]
    text: str


class Conversation(BaseModel):
    messages: list[Message] = Field(default_factory=list)
    brief: GoalBrief | None = None
    status: Status = "asking"
    questions_asked: int = 0


class Node(BaseModel):
    id: str
    title: str
    outcome: Outcome
    severity: Severity | None = None
    detail: str
    evidence_ids: list[str] = Field(default_factory=list)
    finding: str | None = None
    children: list[Node] = Field(default_factory=list)

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()

    def find(self, node_id: str) -> Node | None:
        for node in self.walk():
            if node.id == node_id:
                return node
        return None


class DecisionTree(BaseModel):
    root: Node
    score: int = Field(ge=0, le=100)
    rubric: str
    verdict: str | None = None
    meeting_agenda: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)

    def nodes(self) -> list[Node]:
        return list(self.root.walk())


class Finding(BaseModel):
    node_id: str
    finding: str
    evidence_ids: list[str] = Field(default_factory=list)


class Judgment(BaseModel):
    node_id: str
    outcome: Literal["aligned", "misaligned"]
    severity: Severity | None = None
    finding: str
    evidence_ids: list[str] = Field(default_factory=list)


class AnalystReply(BaseModel):
    findings: list[Finding]
    judgments: list[Judgment] = Field(default_factory=list)
    verdict: str
    meeting_agenda: list[str]
    source_urls: list[str] = Field(default_factory=list)


class AdvisorText(BaseModel):
    headline: str
    why: str
    next_actions: list[str] = Field(min_length=1, max_length=3)


class AdvisorAlert(BaseModel):
    route: Route
    reason: str
    path: list[str] = Field(default_factory=list)
    headline: str | None = None
    why: str | None = None
    next_actions: list[str] = Field(default_factory=list)
    agenda: list[str] = Field(default_factory=list)


class CallRecord(BaseModel):
    task: Literal["intake", "analyst", "advisor"]
    model: str
    effort: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class PipelineTrace(BaseModel):
    stopped: bool
    reason: str | None = None
    calls: list[CallRecord]
