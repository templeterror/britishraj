"""SQLAlchemy 2 models for the `heirloom` schema (blueprint section 5).

Every family-level row carries `organization_id` and `family_id`; rows that fixtures refer to by a
business ref (`asset-family-llc`) also carry `external_ref`, unique per family, with the primary key
derived from it by `ids.ref_id`. JSON columns are wrapped in Mutable* so in-place edits persist.
"""

import uuid
from datetime import UTC, date, datetime
from typing import ClassVar

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

from app.heirloom.db import SCHEMA

FAMILY_ROLES = ("parent", "adult_heir", "advisor", "other")
ASSET_TYPES = (
    "public_equity",
    "real_estate",
    "private_business",
    "partnership",
    "trust_interest",
    "cash",
    "other",
)
LIQUIDITY_CLASSES = ("liquid", "restricted", "illiquid")
ASSET_VERIFIED_STATUSES = ("reported", "verified")
SOURCE_TYPES = ("transcript", "meeting_note", "estate_instrument", "account_statement", "market_publication")
INSTRUMENT_TYPES = (
    "will",
    "trust",
    "beneficiary_designation",
    "ownership_document",
    "letter_of_intent",
    "other",
)
INSTRUMENT_STATUSES = ("draft", "reported", "verified", "superseded")
INTENT_STATUSES = ("proposed", "verified", "superseded", "contested")
DECISION_STATUSES = ("candidate", "verified", "rejected")
GOAL_KINDS = ("business", "home", "education", "philanthropy", "wealth_preservation", "other")
GOAL_FUNDING_SOURCES = ("independent", "conditional_inheritance", "family_support", "unknown")
CONSENT_RESOURCE_TYPES = ("heir_goal", "decision")
# "self": the grantor set it; "advisor_recorded": the advisor recorded the grantor's instruction.
CONSENT_RECORDED_VIA = ("self", "advisor_recorded")
SHARE_SCOPES = (
    "goal_summary",
    "goal_detail",
    "decision_excerpt",
    "asset_identity",
    "estate_intent",
    "balances",
    "none",
)
INSIGHT_TYPES = (
    "liquidity_gap",
    "timing_gap",
    "timing_review",
    "legal_review",
    "distribution_restriction",
    "concentration_risk",
    "missing_intent_evidence",
    "relationship_opportunity",
)
INSIGHT_REVIEW_STATUSES = ("new", "reviewed", "dismissed", "actioned", "invalidated")
ACTION_TYPES = (
    "parent_review",
    "estate_counsel_discussion",
    "heir_intro",
    "planning_meeting",
    "document_request",
)
ACTION_STATUSES = ("draft", "approved", "completed", "cancelled")

MutableJSONDict = MutableDict.as_mutable(JSON)
MutableJSONList = MutableList.as_mutable(JSON)


def utc_now() -> datetime:
    return datetime.now(UTC)


def enum_column(
    name: str,
    values: tuple[str, ...],
    *,
    default: str | None = None,
    nullable: bool = False,
    server_default: str | None = None,
):
    """A VARCHAR column restricted to `values` by a CHECK constraint and by SQLAlchemy at bind time."""
    return mapped_column(
        Enum(*values, name=name, native_enum=False, create_constraint=True, validate_strings=True, length=32),
        default=default,
        nullable=nullable,
        server_default=server_default,
    )


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


def _fk(table: str, *, nullable: bool = False, index: bool = False):
    return mapped_column(Uuid, ForeignKey(f"{SCHEMA}.{table}.id"), nullable=nullable, index=index)


class Family(Base):
    __tablename__ = "families"
    __table_args__: ClassVar = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[str] = mapped_column(String(128), index=True)
    external_ref: Mapped[str | None] = mapped_column(String(128), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    as_of_year: Mapped[int] = mapped_column(Integer)
    preserve_values: Mapped[list[str]] = mapped_column(MutableJSONList, default=list)
    data_revision: Mapped[int] = mapped_column(Integer, default=0)
    consent_revision: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class FamilyRecord(Base):
    """A row scoped to one family inside one organization."""

    __abstract__ = True
    __table_args__: ClassVar = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[str] = mapped_column(String(128))
    family_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey(f"{SCHEMA}.families.id"), index=True)


class RefRecord(FamilyRecord):
    """A family record addressed by a business ref, unique within its family."""

    __abstract__ = True

    external_ref: Mapped[str | None] = mapped_column(String(128))

    @declared_attr.directive
    def __table_args__(cls):
        return (UniqueConstraint("family_id", "external_ref"), {"schema": SCHEMA})


class FamilyPerson(RefRecord):
    __tablename__ = "family_people"

    external_user_id: Mapped[str | None] = mapped_column(String(128), index=True)
    display_name: Mapped[str] = mapped_column(String(200))
    family_role: Mapped[str] = enum_column("family_role", FAMILY_ROLES)
    age: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SourceDocument(RefRecord):
    """Provenance for instruments and decisions. `storage_key` names a file under fixtures/ in demo mode."""

    __tablename__ = "source_documents"

    source_type: Mapped[str] = enum_column("source_type", SOURCE_TYPES)
    title: Mapped[str] = mapped_column(String(300))
    storage_key: Mapped[str] = mapped_column(String(300))
    document_date: Mapped[date] = mapped_column(Date)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    access_class: Mapped[str] = mapped_column(String(64), default="internal_parent_advisor")
    checksum: Mapped[str] = mapped_column(String(64))
    uploaded_by: Mapped[str] = mapped_column(String(128), default="fixture")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Asset(RefRecord):
    __tablename__ = "assets"

    owner_person_id: Mapped[uuid.UUID | None] = _fk("family_people", nullable=True)
    asset_type: Mapped[str] = enum_column("asset_type", ASSET_TYPES)
    label: Mapped[str] = mapped_column(String(300))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    as_of_date: Mapped[date | None] = mapped_column(Date)
    estimated_value: Mapped[int | None] = mapped_column(BigInteger)
    liabilities: Mapped[int | None] = mapped_column(BigInteger)
    liquidity_class: Mapped[str] = enum_column("liquidity_class", LIQUIDITY_CLASSES)
    data_source_id: Mapped[uuid.UUID | None] = _fk("source_documents", nullable=True)
    verified_status: Mapped[str] = enum_column("verified_status", ASSET_VERIFIED_STATUSES, default="reported")
    # Keys: expected_return, annual_volatility, annual_fee, liquidatable_fraction, sale_delay_years,
    # admin_delay_years, sale_cost_fraction, distribution_yield, admin_cost_fraction,
    # partner_consent_required, partner_consent_process_documented (None = unknown).
    terms: Mapped[dict] = mapped_column(MutableJSONDict, default=dict)


class LegalInstrument(RefRecord):
    __tablename__ = "legal_instruments"

    instrument_type: Mapped[str] = enum_column("instrument_type", INSTRUMENT_TYPES)
    title: Mapped[str] = mapped_column(String(300))
    effective_date: Mapped[date | None] = mapped_column(Date)
    reviewed_date: Mapped[date | None] = mapped_column(Date)
    revocable: Mapped[bool | None] = mapped_column(Boolean)
    status: Mapped[str] = enum_column("status", INSTRUMENT_STATUSES, default="reported")
    access_class: Mapped[str] = mapped_column(String(64), default="internal_parent_advisor")
    source_document_id: Mapped[uuid.UUID | None] = _fk("source_documents", nullable=True)
    counsel_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TransferIntent(RefRecord):
    """Documented, mutable intent only; never a transfer of ownership."""

    __tablename__ = "transfer_intents"

    instrument_id: Mapped[uuid.UUID] = _fk("legal_instruments")
    asset_id: Mapped[uuid.UUID] = _fk("assets", index=True)
    beneficiary_person_id: Mapped[uuid.UUID] = _fk("family_people")
    allocation_description: Mapped[str] = mapped_column(Text)
    conditions: Mapped[list[str]] = mapped_column(MutableJSONList, default=list)
    trust_distribution_rule: Mapped[str | None] = mapped_column(Text)
    expected_transfer_window: Mapped[dict | None] = mapped_column(MutableJSONDict)
    advisor_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_by: Mapped[uuid.UUID | None] = _fk("family_people", nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_notes: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = enum_column("status", INTENT_STATUSES, default="proposed")
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)


class DecisionRecord(RefRecord):
    __tablename__ = "decision_records"

    asset_id: Mapped[uuid.UUID] = _fk("assets", index=True)
    person_id: Mapped[uuid.UUID] = _fk("family_people")
    advisor_person_id: Mapped[uuid.UUID] = _fk("family_people")
    decision_date: Mapped[date] = mapped_column(Date)
    action_text: Mapped[str] = mapped_column(Text)
    rationale_text: Mapped[str | None] = mapped_column(Text)  # None = "not documented", never guessed
    rationale_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    alternatives: Mapped[list[str] | None] = mapped_column(MutableJSONList)
    tradeoffs: Mapped[list[str]] = mapped_column(MutableJSONList, default=list)
    source_document_id: Mapped[uuid.UUID] = _fk("source_documents")
    # {page?, start_seconds?, end_seconds?, quoted_span}
    source_locator: Mapped[dict] = mapped_column(MutableJSONDict, default=dict)
    extraction_confidence: Mapped[float | None] = mapped_column(Float)
    verification_status: Mapped[str] = enum_column(
        "verification_status", DECISION_STATUSES, default="candidate"
    )
    verified_by: Mapped[uuid.UUID | None] = _fk("family_people", nullable=True)
    advisor_note: Mapped[str | None] = mapped_column(Text)
    external_event_id: Mapped[str | None] = mapped_column(String(200), unique=True)
    valid_from: Mapped[date | None] = mapped_column(Date)
    valid_to: Mapped[date | None] = mapped_column(Date)


class HeirGoal(RefRecord):
    __tablename__ = "heir_goals"

    heir_person_id: Mapped[uuid.UUID] = _fk("family_people", index=True)
    goal_kind: Mapped[str] = enum_column("goal_kind", GOAL_KINDS)
    description_private: Mapped[str] = mapped_column(Text)
    amount_target: Mapped[int | None] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    target_year: Mapped[int | None] = mapped_column(Integer)
    horizon_min_years: Mapped[int | None] = mapped_column(Integer)
    horizon_max_years: Mapped[int | None] = mapped_column(Integer)
    milestone: Mapped[str | None] = mapped_column(Text)
    goal_funding_source: Mapped[str] = enum_column(
        "goal_funding_source", GOAL_FUNDING_SOURCES, default="unknown"
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class ConsentGrant(FamilyRecord):
    __tablename__ = "consent_grants"

    grantor_person_id: Mapped[uuid.UUID] = _fk("family_people", index=True)
    recipient_person_id: Mapped[uuid.UUID] = _fk("family_people")
    resource_type: Mapped[str] = enum_column("resource_type", CONSENT_RESOURCE_TYPES)
    # A heir_goal or decision id (polymorphic, so no FK).
    resource_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    share_scope: Mapped[str] = enum_column("share_scope", SHARE_SCOPES)
    purpose: Mapped[str] = mapped_column(String(200), default="")
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, default=0)
    recorded_by: Mapped[str] = mapped_column(String(128))
    # Provenance of the latest change. An advisor-recorded change always cites the conversation it came
    # from; `basis_note` is advisor-only and never reaches an heir-facing response.
    recorded_via: Mapped[str] = enum_column(
        "recorded_via", CONSENT_RECORDED_VIA, default="self", server_default="self"
    )
    basis_note: Mapped[str | None] = mapped_column(String(500))
    basis_date: Mapped[date | None] = mapped_column(Date)
    basis_source_id: Mapped[uuid.UUID | None] = _fk("source_documents", nullable=True)


class ForecastScenario(FamilyRecord):
    __tablename__ = "forecast_scenarios"

    asset_id: Mapped[uuid.UUID] = _fk("assets")
    goal_id: Mapped[uuid.UUID | None] = _fk("heir_goals", nullable=True)
    settings: Mapped[dict] = mapped_column(MutableJSONDict, default=dict)
    inputs_as_of: Mapped[date | None] = mapped_column(Date)
    market_source_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    seed: Mapped[int] = mapped_column(Integer)
    model_version: Mapped[str] = mapped_column(String(64))
    requested_by: Mapped[str] = mapped_column(String(128), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    status: Mapped[str] = mapped_column(String(32), default="complete")


class ForecastResult(FamilyRecord):
    __tablename__ = "forecast_results"

    scenario_id: Mapped[uuid.UUID] = _fk("forecast_scenarios", index=True)
    percentiles: Mapped[dict] = mapped_column(MutableJSONDict, default=dict)
    accessible_proceeds: Mapped[dict] = mapped_column(MutableJSONDict, default=dict)
    goal_shortfall_metrics: Mapped[dict] = mapped_column(MutableJSONDict, default=dict)
    limitations: Mapped[list[str]] = mapped_column(MutableJSONList, default=list)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    stale: Mapped[bool] = mapped_column(Boolean, default=False)


class Insight(FamilyRecord):
    __tablename__ = "insights"

    insight_key: Mapped[str] = mapped_column(String(200), index=True)
    input_hash: Mapped[str] = mapped_column(String(64), default="")
    type: Mapped[str] = enum_column("type", INSIGHT_TYPES)
    title: Mapped[str] = mapped_column(String(300))
    advisor_safe_summary: Mapped[str] = mapped_column(Text, default="")
    filter_tags: Mapped[list[str]] = mapped_column(MutableJSONList, default=list)
    payload: Mapped[dict] = mapped_column(MutableJSONDict, default=dict)
    review_status: Mapped[str] = enum_column("review_status", INSIGHT_REVIEW_STATUSES, default="new")
    visibility_scope: Mapped[str] = mapped_column(String(64), default="advisor_only")
    consent_revision: Mapped[int] = mapped_column(Integer, default=0)
    model_version: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AdvisorAction(FamilyRecord):
    __tablename__ = "advisor_actions"

    insight_id: Mapped[uuid.UUID] = _fk("insights", index=True)
    advisor_person_id: Mapped[uuid.UUID] = _fk("family_people")
    action_type: Mapped[str] = enum_column("action_type", ACTION_TYPES)
    draft_text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = enum_column("status", ACTION_STATUSES, default="draft")
    reviewed_by: Mapped[uuid.UUID | None] = _fk("family_people", nullable=True)
    outcome_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class MarketEvent(FamilyRecord):
    __tablename__ = "market_events"

    asset_id: Mapped[uuid.UUID] = _fk("assets", index=True)
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(String(500))
    published_at: Mapped[date] = mapped_column(Date)
    summary: Mapped[str] = mapped_column(Text, default="")
    proposed_stress: Mapped[str | None] = mapped_column(String(32))


class DomainEvent(FamilyRecord):
    __tablename__ = "domain_events"

    type: Mapped[str] = mapped_column(String(100), index=True)
    aggregate_id: Mapped[str] = mapped_column(String(200))
    event_version: Mapped[int] = mapped_column(Integer, default=1)
    event_payload: Mapped[dict] = mapped_column(MutableJSONDict, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(300), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AuditLog(Base):
    """Allowed and denied reads/writes. `family_id` is deliberately not a FK: forged ids are logged too."""

    __tablename__ = "audit_log"
    __table_args__: ClassVar = {"schema": SCHEMA}

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[str] = mapped_column(String(128))
    actor_external_id: Mapped[str] = mapped_column(String(128), index=True)
    family_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    action: Mapped[str] = mapped_column(String(100))
    resource_type: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[str | None] = mapped_column(String(200))
    allowed: Mapped[bool] = mapped_column(Boolean)
    reason_code: Mapped[str] = mapped_column(String(100))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
