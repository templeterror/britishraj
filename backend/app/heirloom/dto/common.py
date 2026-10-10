"""Response shapes shared by more than one audience.

Every DTO forbids extra fields: an audience's model lists exactly what that audience may see, so a
field that is not declared cannot leak into a response.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.heirloom.graph.repository import GEdge, GNode

Role = Literal["advisor", "parent", "adult_heir"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FamilyDTO(StrictModel):
    id: str
    display_name: str
    as_of_year: int


class PersonRef(StrictModel):
    id: str
    display_name: str
    role: Role


class PersonDTO(StrictModel):
    id: str
    ref: str | None
    display_name: str
    role: str
    age: int | None


class AssetTerms(StrictModel):
    """`None` means the term is unknown (needs attorney review), never zero."""

    expected_return: float | None = None
    annual_volatility: float | None = None
    annual_fee: float | None = None
    liquidatable_fraction: float | None = None
    sale_delay_years: float | None = None
    admin_delay_years: float | None = None
    sale_cost_fraction: float | None = None
    distribution_yield: float | None = None
    admin_cost_fraction: float | None = None
    partner_consent_required: bool | None = None
    partner_consent_process_documented: bool | None = None


class AssetDTO(StrictModel):
    id: str
    ref: str | None
    label: str
    asset_kind: str
    liquidity_class: str
    currency: str
    as_of_date: date | None
    value: int | None
    liabilities: int | None
    verified_status: str
    terms: AssetTerms


class IntentDTO(StrictModel):
    id: str
    ref: str | None
    instrument_ref: str | None
    asset_ref: str | None
    beneficiary_id: str
    beneficiary_display_name: str
    allocation: str
    conditions: list[str]
    status: str
    advisor_verified: bool
    verified_by_display: str | None
    verification_notes: str | None
    confidence: float | None
    valid_from: date | None
    valid_to: date | None
    counsel_reviewed_at: datetime | None


class DecisionDTO(StrictModel):
    id: str
    ref: str | None
    decision_date: date
    asset_ref: str | None
    action: str
    rationale: str | None  # None = "Rationale not documented"
    alternatives: list[str]
    verification_status: str
    rationale_edited: bool
    advisor_note: str | None
    valid_to: date | None
    confidence: float | None
    source_title: str | None
    locator: dict | None
    verified_by_display: str | None


class GraphDTO(StrictModel):
    nodes: list[GNode]
    edges: list[GEdge]
    evidence_refs: list[str]
    revision: int


EvidenceKind = Literal["estate_instrument", "estate_intent", "asset", "decision", "goal"]


class EvidenceDTO(StrictModel):
    record_ref: str
    title: str
    kind: EvidenceKind
    status: str
    qualifier: str | None
    document_title: str | None
    document_date: date | None
    excerpt: str | None
    locator: dict | None
