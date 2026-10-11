"""The background readiness pipeline: recompute a family's insights on every relevant domain event.

`recompute` builds one `AuthorizedAlignmentContext` per (current intent naming the heir, heir goal),
runs the scenario grid where the classifier needs one, stores each grid cell as a forecast scenario,
and upserts the classifier's drafts as insights. Heir goals reach it only through
`consent.goal_view_for_advisor`, so an unshared goal yields no forecast and no insight at all.
"""

import dataclasses
import hashlib
import json
import threading
from collections import OrderedDict
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.heirloom.config import get_settings
from app.heirloom.models import (
    Asset,
    DecisionRecord,
    DomainEvent,
    Family,
    ForecastResult,
    ForecastScenario,
    HeirGoal,
    Insight,
    LegalInstrument,
    TransferIntent,
)
from app.heirloom.services import classifier, consent, events
from app.heirloom.services.classifier import (
    AssetFacts,
    AuthorizedAlignmentContext,
    Grid,
    InsightDraft,
    IntentFacts,
    RecordFacts,
)
from app.heirloom.services.graph import record_ref, restriction_label
from app.heirloom.simulation import engine
from app.heirloom.simulation.engine import AssetTerms, ScenarioInput

TRIGGERS = (
    "estate_intent.*",
    "instrument.status_changed.v1",  # superseding an instrument ends its intents
    "decision.verified.v1",
    "heir_goal.updated.v1",
    consent.CONSENT_CHANGED,  # registered after the consent handler, which withdraws stale insights first
    "asset.terms_updated.v1",
    "market_context.updated.v1",
    "alignment.candidate_accepted.v1",
)
TRANSFER_YEARS = (10, 20, 30)
MIN_HORIZON_YEARS = 30
_GRID_CACHE_SIZE = 64

# (base input hash, consent revision) -> grid. Results are deterministic, so a hit is exact.
_grid_cache: OrderedDict[tuple[str, int], Grid] = OrderedDict()
_grid_cache_lock = threading.Lock()


@dataclasses.dataclass(frozen=True)
class RecomputeResult:
    created: int
    kept: int
    invalidated: int


# --- Context -----------------------------------------------------------------------------------


def _engine_terms(asset: Asset) -> AssetTerms:
    """The engine's view of the asset. Unknown access terms stay unknown (the engine returns no probability)."""
    terms = asset.terms or {}

    def number(key: str) -> float:
        value = terms.get(key)
        return 0.0 if value is None else float(value)

    fraction, delay = terms.get("liquidatable_fraction"), terms.get("sale_delay_years")
    return AssetTerms(
        starting_value=float(asset.estimated_value or 0),
        attributable_debt=float(asset.liabilities or 0),
        expected_return=number("expected_return"),
        annual_volatility=number("annual_volatility"),
        annual_fee=number("annual_fee"),
        liquidatable_fraction=None if fraction is None else float(fraction),
        sale_delay_years=None if delay is None else int(delay),
        admin_delay_years=int(number("admin_delay_years")),
        sale_cost_fraction=number("sale_cost_fraction"),
        distribution_yield=number("distribution_yield"),
        admin_cost_fraction=number("admin_cost_fraction"),
        # Unknown whether partner consent is needed counts as needed, and undocumented.
        partner_consent_required=terms.get("partner_consent_required") is not False,
        partner_consent_process_documented=terms.get("partner_consent_process_documented") is True,
    )


def _intent_verified(intent: TransferIntent, instrument: LegalInstrument | None) -> bool:
    """Advisor-verified and still current on a verified instrument; a contested intent still counts."""
    return (
        intent.advisor_verified
        and intent.status in ("verified", "contested")
        and intent.valid_to is None
        and instrument is not None
        and instrument.status == "verified"
    )


def _current_verified_decisions(session: Session, family: Family, asset: Asset) -> list[DecisionRecord]:
    return list(
        session.scalars(
            select(DecisionRecord)
            .where(
                DecisionRecord.family_id == family.id,
                DecisionRecord.asset_id == asset.id,
                DecisionRecord.verification_status == "verified",
                DecisionRecord.valid_to.is_(None),  # an ended decision is history, not the current rationale
            )
            .order_by(DecisionRecord.decision_date.desc(), DecisionRecord.id)
        )
    )


def build_context(
    session: Session, family: Family, intent: TransferIntent | None, goal: HeirGoal
) -> AuthorizedAlignmentContext:
    """The only way to build a classifier context: the goal passes the advisor consent gate here."""
    common = {
        "family_ref": family.external_ref or str(family.id),
        "as_of_year": family.as_of_year,
        "consent_revision": family.consent_revision,
    }
    view = consent.goal_view_for_advisor(session, family, goal)
    if view is None:
        return AuthorizedAlignmentContext(
            **common, intent=None, conflict=False, asset=None, goal=None, decision_refs=[]
        )
    if intent is None:
        return AuthorizedAlignmentContext(
            **common,
            intent=None,
            conflict=False,
            asset=None,
            goal=view,
            decision_refs=[],
            goal_ref=record_ref(goal),
        )

    instrument = session.get(LegalInstrument, intent.instrument_id)
    asset = session.get(Asset, intent.asset_id)
    decisions = _current_verified_decisions(session, family, asset)
    latest = decisions[0] if decisions else None
    return AuthorizedAlignmentContext(
        **common,
        intent=IntentFacts(
            ref=record_ref(intent),
            label=intent.allocation_description,
            status=intent.status,
            verified=_intent_verified(intent, instrument),
            instrument=RecordFacts(record_ref(instrument), instrument.title, instrument.status)
            if instrument
            else None,
        ),
        conflict=intent.status == "contested",
        asset=AssetFacts(
            ref=record_ref(asset),
            label=asset.label,
            status=asset.verified_status,
            terms=_engine_terms(asset),
            restriction=restriction_label(asset) or None,
            latest_decision=(
                RecordFacts(record_ref(latest), latest.action_text, latest.verification_status)
                if latest
                else None
            ),
        ),
        goal=view,
        decision_refs=[record_ref(d) for d in decisions],
        goal_ref=record_ref(goal),
    )


# --- Forecast grid -----------------------------------------------------------------------------


def _grid(ctx: AuthorizedAlignmentContext, goal_year: int, amount: int) -> tuple[ScenarioInput, Grid]:
    base = ScenarioInput(
        terms=ctx.asset.terms,
        transfer_year=TRANSFER_YEARS[0],
        goal_year=goal_year,
        goal_amount_today=float(amount),
        horizon_years=max(MIN_HORIZON_YEARS, goal_year),
    )
    key = (engine.input_hash(base), ctx.consent_revision)
    with _grid_cache_lock:
        if key in _grid_cache:
            _grid_cache.move_to_end(key)
            return base, _grid_cache[key]
    grid = engine.run_grid(base, TRANSFER_YEARS)
    with _grid_cache_lock:
        _grid_cache[key] = grid
        while len(_grid_cache) > _GRID_CACHE_SIZE:
            _grid_cache.popitem(last=False)
    return base, grid


def _quantiles(series) -> list[dict]:
    return [dataclasses.asdict(q) for q in series]


def _store_grid(
    session: Session,
    family: Family,
    ctx: AuthorizedAlignmentContext,
    intent: TransferIntent,
    goal: HeirGoal,
    base: ScenarioInput,
    grid: Grid,
) -> set[UUID]:
    """Persist each cell under its classifier scenario id; an identical cell already stored is kept."""
    scope = {"organization_id": family.organization_id, "family_id": family.id}
    asset = session.get(Asset, intent.asset_id)
    cells = {UUID(classifier.scenario_id(ctx, result)): (cell, result) for cell, result in grid.items()}
    new = {sid: entry for sid, entry in cells.items() if session.get(ForecastScenario, sid) is None}
    if not new:
        return set(cells)
    for sid, ((year, preset), result) in new.items():
        session.add(
            ForecastScenario(
                id=sid,
                asset_id=asset.id,
                goal_id=goal.id,
                settings=dataclasses.asdict(dataclasses.replace(base, transfer_year=year, preset=preset)),
                inputs_as_of=asset.as_of_date,
                seed=result.seed,
                model_version=result.model_version,
                **scope,
            )
        )
    session.flush()  # no ORM relationship orders the inserts, so scenarios go in before their results
    for sid, (_cell, result) in new.items():
        session.add(
            ForecastResult(
                scenario_id=sid,
                percentiles={
                    "value_nominal": _quantiles(result.value_nominal),
                    "value_real": _quantiles(result.value_real),
                },
                accessible_proceeds={
                    "cash_by_year": _quantiles(result.cash_by_year),
                    "cash_at_goal": dataclasses.asdict(result.cash_at_goal),
                    "sale_completion_year": result.sale_completion_year,
                    "admin_cost_at_transfer_p50": result.admin_cost_at_transfer_p50,
                },
                goal_shortfall_metrics={
                    "goal_nominal": result.goal_nominal,
                    "p_cash_covers_goal": result.p_cash_covers_goal,
                    "shortfall_share": result.shortfall_share,
                    "transfer_after_goal": result.transfer_after_goal,
                },
                limitations=list(result.limitations),
                **scope,
            )
        )
    return set(cells)


def _drop_scenarios_except(session: Session, family: Family, keep: set[UUID]) -> None:
    """Forecasts no current pair needs are deleted, so a revoked goal leaves no derived forecast behind."""
    stale = [
        sid
        for sid in session.scalars(select(ForecastScenario.id).where(ForecastScenario.family_id == family.id))
        if sid not in keep
    ]
    if stale:
        session.execute(delete(ForecastResult).where(ForecastResult.scenario_id.in_(stale)))
        session.execute(delete(ForecastScenario).where(ForecastScenario.id.in_(stale)))


# --- Insights ----------------------------------------------------------------------------------


def _draft_hash(draft: InsightDraft, consent_revision: int) -> str:
    payload = {
        "model_version": engine.MODEL_VERSION,
        "consent_revision": consent_revision,
        "draft": dataclasses.asdict(draft),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _insight(family: Family, draft: InsightDraft, input_hash: str) -> Insight:
    return Insight(
        organization_id=family.organization_id,
        family_id=family.id,
        insight_key=draft.insight_key,
        input_hash=input_hash,
        type=draft.type,
        title=draft.title,
        advisor_safe_summary=draft.summary,
        filter_tags=list(draft.filter_tags),
        payload={
            "why_now": draft.why_now,
            "known": draft.known,
            "conditional": draft.conditional,
            "contact": draft.contact,
            "headline_probability": draft.headline_probability,
            "headline_condition": draft.headline_condition,
            "scenario_rows": draft.scenario_rows,
            "evidence": draft.evidence,
            "goal_ref": draft.goal_ref,
            "assumptions": draft.assumptions,
        },
        review_status="new",
        visibility_scope="advisor_only",
        consent_revision=family.consent_revision,
        model_version=engine.MODEL_VERSION,
    )


def _upsert_insights(session: Session, family: Family, drafts: list[InsightDraft]) -> RecomputeResult:
    """Same key and input hash keeps the row (and its review status); a changed draft replaces it."""
    active = {
        row.insight_key: row
        for row in session.scalars(
            select(Insight).where(Insight.family_id == family.id, Insight.review_status != "invalidated")
        )
    }
    created = kept = invalidated = 0
    for draft in drafts:
        input_hash = _draft_hash(draft, family.consent_revision)
        row = active.pop(draft.insight_key, None)
        if row is not None and row.input_hash == input_hash:
            kept += 1
            continue
        if row is not None:
            row.review_status = "invalidated"
            invalidated += 1
        session.add(_insight(family, draft, input_hash))
        created += 1
    for row in active.values():  # active insights this run did not produce
        row.review_status = "invalidated"
        invalidated += 1
    return RecomputeResult(created=created, kept=kept, invalidated=invalidated)


def _current_intents(session: Session, family: Family, heir_person_id: UUID) -> list[TransferIntent]:
    return list(
        session.scalars(
            select(TransferIntent)
            .where(
                TransferIntent.family_id == family.id,
                TransferIntent.beneficiary_person_id == heir_person_id,
                TransferIntent.status != "superseded",
                TransferIntent.valid_to.is_(None),
            )
            .order_by(TransferIntent.valid_from, TransferIntent.id)
        )
    )


def recompute(session: Session, family: Family, threshold: float | None = None) -> RecomputeResult:
    """Bring the family's forecasts and insights in line with its current, consented records."""
    threshold = get_settings().review_threshold if threshold is None else threshold
    drafts: dict[str, InsightDraft] = {}
    scenario_ids: set[UUID] = set()
    goals = list(
        session.scalars(
            select(HeirGoal)
            .where(HeirGoal.family_id == family.id)
            .order_by(HeirGoal.external_ref, HeirGoal.id)
        )
    )
    for goal in goals:
        for intent in _current_intents(session, family, goal.heir_person_id) or [None]:
            ctx = build_context(session, family, intent, goal)
            grid = None
            inputs = classifier.model_inputs(ctx)
            if inputs is not None:
                base, grid = _grid(ctx, *inputs)
                scenario_ids |= _store_grid(session, family, ctx, intent, goal, base, grid)
            for draft in classifier.classify(ctx, grid, threshold):
                drafts.setdefault(
                    draft.insight_key, draft
                )  # a goal-only insight is the same for every intent

    _drop_scenarios_except(session, family, scenario_ids)
    result = _upsert_insights(session, family, list(drafts.values()))
    session.flush()
    return result


def _on_event(session: Session, family: Family, _event: DomainEvent) -> None:
    recompute(session, family)


def register_handlers() -> None:
    """Idempotent (`events.register` ignores duplicates). Call after `consent.register_handlers`."""
    for trigger in TRIGGERS:
        events.register(trigger, _on_event)
