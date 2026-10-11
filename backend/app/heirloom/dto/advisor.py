from datetime import date, datetime
from typing import Literal
from uuid import UUID

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


class SourceRef(StrictModel):
    """A family conversation record the advisor can cite as the basis of a recorded instruction."""

    ref: str
    title: str
    document_date: date
    source_type: str


class AdvisorSharingPolicy(StrictModel):
    estate_intent: Literal["off"] = "off"
    balances: Literal["not_available_in_pilot"] = "not_available_in_pilot"


class HeirSharingView(StrictModel):
    """Whether a verified decision reaches the family's heir, and the provenance of the latest change.

    Advisor-only: `basis_note` is what the advisor wrote down from the parent's conversation.
    """

    shared: bool
    recipient_person_id: UUID
    recipient_display: str
    recorded_via: Literal["self", "advisor_recorded"] | None
    recorded_by_display: str | None
    basis_date: date | None
    basis_note: str | None
    basis_source_ref: str | None
    basis_source_title: str | None
    updated_at: datetime | None


class AdvisorDecisionDTO(DecisionDTO):
    heir_sharing: HeirSharingView | None  # None unless the decision is verified


class AdvisorSnapshot(StrictModel):
    family: FamilyDTO
    advisor: PersonRef
    people: list[PersonDTO]
    assets: list[AdvisorAssetDTO]
    instruments: list[InstrumentDTO]
    intents: list[IntentDTO]
    decisions: list[AdvisorDecisionDTO]
    goal_sharing: Literal["not_shared", "summary", "detail"]
    # Detail first: pydantic's smart union keeps a detail view's extra fields.
    shared_goals: list[AdvisorGoalDetail | AdvisorGoalSummary]
    coverage: CoverageDTO
    open_flags: int
    preserve_values: list[str]
    sources: list[SourceRef]
    sharing_policy: AdvisorSharingPolicy
