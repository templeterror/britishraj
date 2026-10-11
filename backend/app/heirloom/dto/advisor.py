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
from app.heirloom.models import INSIGHT_REVIEW_STATUSES
from app.heirloom.simulation.scenarios import StressPreset


class AdvisorGoalSummary(StrictModel):
    """What a `goal_summary` grant shows the advisor: kind and bands, never the narrative or amount."""

    goal_id: str
    kind: str
    horizon_band: str
    amount_band: str
    amount_band_mid: int | None  # None when the heir set no amount: never modeled as zero
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


InsightType = Literal["liquidity_gap", "timing_gap", "timing_review", "legal_review", "relationship_opportunity"]
FilterTag = Literal["needs_parent_review", "heir_conversation", "legal_source_conflict", "scenario_mismatch"]
InsightEvidenceKind = Literal["estate_instrument", "estate_intent", "asset", "decision", "goal", "forecast"]


class ScenarioRowDTO(StrictModel):
    """One grid cell behind an insight; `scenario_id` is what `GET /forecasts/{scenario_id}` takes."""

    transfer_year: int
    preset: StressPreset
    p: float | None  # None: access terms unknown, never a reassuring number
    cash_p50: float
    value_p50: float
    scenario_id: str


class InsightEvidenceDTO(StrictModel):
    kind: InsightEvidenceKind
    ref: str
    label: str
    status: str


class InsightDTO(StrictModel):
    id: str
    type: InsightType
    insight_key: str
    title: str
    summary: str
    why_now: str
    known: list[str]
    conditional: list[str]
    contact: list[str]
    headline_probability: float | None
    headline_condition: str
    scenario_rows: list[ScenarioRowDTO]
    evidence: list[InsightEvidenceDTO]
    filter_tags: list[FilterTag]
    goal_ref: str | None
    assumptions: dict
    review_status: Literal[INSIGHT_REVIEW_STATUSES]
    consent_revision: int
    created_at: datetime


class YearQuantilesDTO(StrictModel):
    year: int
    p10: float
    p50: float
    p90: float


class ScenarioResultDTO(StrictModel):
    """A stored forecast run: every engine `ScenarioResult` field, its engine input and when it ran."""

    value_nominal: list[YearQuantilesDTO]
    value_real: list[YearQuantilesDTO]
    cash_by_year: list[YearQuantilesDTO]
    cash_at_goal: YearQuantilesDTO
    goal_nominal: float
    p_cash_covers_goal: float | None
    shortfall_share: float | None
    sale_completion_year: int | None
    transfer_after_goal: bool
    admin_cost_at_transfer_p50: float
    limitations: list[str]
    seed: int
    model_version: str
    input_hash: str
    settings: dict
    computed_at: datetime
