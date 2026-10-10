from datetime import date, datetime
from typing import Literal

from app.heirloom.dto.common import (
    AssetDTO,
    DecisionDTO,
    FamilyDTO,
    IntentDTO,
    PersonDTO,
    PersonRef,
    StrictModel,
)


class AdvisorGoalSummary(StrictModel):
    """What a `goal_summary` grant shows the advisor: kind and bands, never the narrative or amount."""

    goal_id: str
    kind: str
    horizon_band: str
    amount_band: str
    amount_band_mid: int
    horizon_max_years: int | None


class AdvisorGoalDetail(AdvisorGoalSummary):
    """A `goal_detail` grant adds the exact figures and the heir's own words."""

    amount_target: int | None
    target_year: int | None
    milestone: str | None
    description: str


class MarketEventDTO(StrictModel):
    title: str
    url: str
    published_at: date
    proposed_stress: str | None


class AdvisorAssetDTO(AssetDTO):
    market_events: list[MarketEventDTO]


class InstrumentDTO(StrictModel):
    id: str
    ref: str | None
    title: str
    kind: str
    status: str
    effective_date: date | None
    revocable: bool | None
    counsel_reviewed_at: datetime | None
    source_title: str | None
    source_excerpt: str | None
    source_version: int | None


class CoverageDTO(StrictModel):
    decisions_verified: int
    decisions_total: int
    assets_with_verified_intent: int
    assets_total: int
    heirs_connected: int
    heirs_total: int


class AdvisorSnapshot(StrictModel):
    family: FamilyDTO
    advisor: PersonRef
    people: list[PersonDTO]
    assets: list[AdvisorAssetDTO]
    instruments: list[InstrumentDTO]
    intents: list[IntentDTO]
    decisions: list[DecisionDTO]
    goal_sharing: Literal["not_shared", "summary", "detail"]
    # Detail first: pydantic's smart union keeps a detail view's extra fields.
    shared_goals: list[AdvisorGoalDetail | AdvisorGoalSummary]
    coverage: CoverageDTO
    open_flags: int
