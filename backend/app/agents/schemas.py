"""Decisions and traces for one analysis run."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


SliceName = Literal["quotes", "home", "comps", "funding"]


class IntakeBrief(BaseModel):
    amount_usd: float | None = None
    horizon: str | None = None
    intent: str
    slices: list[SliceName] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    ambiguous: bool = False


class TriageDecision(BaseModel):
    stop: bool
    reason: str
    slices: list[SliceName] = Field(default_factory=list)
    clarity: Literal["clear", "ambiguous"]


class Alert(BaseModel):
    severity: Literal["low", "medium", "high"]
    claim: str
    verdict: str
    agenda: list[str]


class CallRecord(BaseModel):
    task: Literal["intake", "analyst"]
    model: str
    effort: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class PipelineTrace(BaseModel):
    stopped: bool
    calls: list[CallRecord]
