"""The deterministic readiness classifier (blueprint §7): one advisor-side context in, insight drafts out.

Pure: no database, clock or randomness, so the same context and grid always give the same drafts and
the readiness pipeline can tell an unchanged insight from a changed one by hashing them.

The context holds only what the advisor may see. The heir goal arrives as the consented advisor view
(`consent.goal_view_for_advisor`), never as the heir's private record. Forecast copy always reads
"if transfer were to occur in year N" and is labeled illustrative: a transfer is never predicted.
"""

from dataclasses import dataclass

from app.heirloom.dto.advisor import AdvisorGoalDetail, AdvisorGoalSummary, FilterTag, InsightType
from app.heirloom.ids import ref_id
from app.heirloom.simulation.engine import UNKNOWN_TERMS_NOTE, AssetTerms, ScenarioResult
from app.heirloom.simulation.scenarios import PRESETS

Grid = dict[tuple[int, str], ScenarioResult]

FILTER_TAGS: dict[str, list[FilterTag]] = {
    "liquidity_gap": ["needs_parent_review", "scenario_mismatch"],
    "timing_gap": ["heir_conversation", "scenario_mismatch"],
    "timing_review": ["needs_parent_review"],
    "legal_review": ["legal_source_conflict"],
    "relationship_opportunity": ["heir_conversation"],
}
INSUFFICIENT_DATA = "Insufficient modeling data: goal timing or amount not shared"
INSUFFICIENT_TERMS = "Insufficient modeling data: asset valuation or terms not recorded"
UNKNOWN_TERMS = "Access terms unknown — attorney review"
NO_MISMATCH = "No modeled mismatch under these assumptions"
HYPOTHETICAL_TIMING = "Transfer timing is hypothetical; no mortality is modeled"
INTENT_MAY_CHANGE = "Assumes the current documented intent stays in place; it can be amended"

# How each stress preset reads after "if transfer were to occur in year N".
PRESET_CONDITION = {
    "base": "under base assumptions",
    "exit_delay_24m": "and the exit took 24 months longer",
    "shock_30_y1": "after a 30% value drop in year 1",
    "sale_haircut_20": "with a 20% haircut on the sale",
}
PRESET_LABEL = {
    "base": "base",
    "exit_delay_24m": "exit +24 months",
    "shock_30_y1": "−30% year-1 shock",
    "sale_haircut_20": "20% sale haircut",
}


@dataclass(frozen=True)
class RecordFacts:
    """An advisor-visible record an insight can cite: its graph/evidence ref, label and status."""

    ref: str
    label: str
    status: str


@dataclass(frozen=True)
class IntentFacts:
    ref: str
    label: str  # the allocation, e.g. "Robert's 40% membership interest"
    status: str  # TransferIntent.status
    verified: bool  # advisor-verified, still current, on a verified instrument (it may still be contested)
    instrument: RecordFacts | None


@dataclass(frozen=True)
class AssetFacts:
    ref: str
    label: str
    status: str
    terms: AssetTerms | None  # None: the valuation or a required modeling term is not recorded
    restriction: str | None  # e.g. "Partner consent required; 25% liquidatable"
    latest_decision: RecordFacts | None  # the newest current verified decision on the asset
    missing_terms: tuple[str, ...] = ()  # what is not recorded, e.g. ("estimated value",)


@dataclass(frozen=True)
class AuthorizedAlignmentContext:
    """What the classifier may use about one (intent, heir goal) pair. Built by `readiness.build_context`."""

    family_ref: str
    as_of_year: int
    intent: IntentFacts | None
    conflict: bool
    asset: AssetFacts | None  # None exactly when `intent` is None
    goal: AdvisorGoalSummary | AdvisorGoalDetail | None  # None: the heir has not shared the goal
    decision_refs: list[str]  # current verified decisions on the asset, newest first
    consent_revision: int
    goal_ref: str | None = None  # the shared goal's graph/evidence ref


@dataclass(frozen=True)
class InsightDraft:
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
    scenario_rows: list[dict]  # {transfer_year, preset, p, cash_p50, value_p50, scenario_id}
    evidence: list[dict]  # {kind, ref, label, status}
    filter_tags: list[FilterTag]
    goal_ref: str | None
    assumptions: dict


# --- Modeling inputs ---------------------------------------------------------------------------


def goal_year(ctx: AuthorizedAlignmentContext) -> int | None:
    """Years from `as_of_year` to the goal: the shared horizon's upper bound, else the shared target year."""
    goal = ctx.goal
    if goal is None:
        return None
    if goal.horizon_max_years is not None:
        return goal.horizon_max_years
    target = goal.target_year if isinstance(goal, AdvisorGoalDetail) else None
    return None if target is None else target - ctx.as_of_year


def goal_amount(goal: AdvisorGoalSummary | AdvisorGoalDetail) -> int | None:
    """The exact amount under a detail grant, else the midpoint of the shared amount band."""
    return goal.amount_target if isinstance(goal, AdvisorGoalDetail) else goal.amount_band_mid


def model_inputs(ctx: AuthorizedAlignmentContext) -> tuple[int, int] | None:
    """`(goal year, goal amount today)` when classifying `ctx` needs a forecast grid, else None.

    None also when the asset's valuation or a modeling term is not recorded: a missing number is never
    modeled as zero, which would read as a precise 0% or 100%.
    """
    if ctx.goal is None or ctx.intent is None or not ctx.intent.verified or ctx.conflict:
        return None
    if ctx.asset.terms is None:
        return None
    year, amount = goal_year(ctx), goal_amount(ctx.goal)
    return None if year is None or amount is None else (year, amount)


def scenario_id(ctx: AuthorizedAlignmentContext, result: ScenarioResult) -> str:
    """The `forecast_scenarios` id of one grid cell of this pair; the pipeline persists the cell under it.

    Deterministic, so an identical recompute cites the same scenarios, and a new consent revision
    never reuses a scenario computed under an older one.
    """
    parts = ("forecast", ctx.family_ref, ctx.asset.ref, ctx.goal_ref or "", str(ctx.consent_revision))
    return str(ref_id(":".join((*parts, result.input_hash))))


# --- Copy helpers ------------------------------------------------------------------------------


def _pct(p: float) -> str:
    return f"{p:.0%}"


def _kind(ctx: AuthorizedAlignmentContext) -> str:
    return ctx.goal.kind.replace("_", " ")


def _bands(ctx: AuthorizedAlignmentContext) -> str:
    return f"{ctx.goal.amount_band}, {ctx.goal.horizon_band}"


def _condition(year: int, preset: str) -> str:
    return f"if transfer were to occur in year {year} {PRESET_CONDITION[preset]}"


def _headline(goal_year_: int, cell: tuple[int, str]) -> str:
    return f"Chance accessible cash covers the goal in year {goal_year_} {_condition(*cell)} (illustrative)"


def _order(cell: tuple[int, str]) -> tuple[int, int]:
    return cell[0], PRESETS.index(cell[1])


def _cells(grid: Grid) -> list[tuple[int, str]]:
    return sorted(grid, key=_order)


def _eligible(grid: Grid, year: int) -> list[tuple[int, str]]:
    """Cells whose transfer could fund a goal in `year`. A later transfer is a timing question, not a 0%."""
    return [cell for cell in _cells(grid) if cell[0] <= year]


# --- Evidence and rows -------------------------------------------------------------------------


def _record(kind: str, record: RecordFacts) -> dict:
    return {"kind": kind, "ref": record.ref, "label": record.label, "status": record.status}


def _goal_evidence(ctx: AuthorizedAlignmentContext) -> dict:
    status = "shared_detail" if isinstance(ctx.goal, AdvisorGoalDetail) else "shared_summary"
    label = f"{_kind(ctx).capitalize()} goal ({_bands(ctx)})"
    return {"kind": "goal", "ref": ctx.goal_ref, "label": label, "status": status}


def _estate_evidence(ctx: AuthorizedAlignmentContext) -> list[dict]:
    intent, asset = ctx.intent, ctx.asset
    items = [_record("estate_instrument", intent.instrument)] if intent.instrument else []
    items.append({"kind": "estate_intent", "ref": intent.ref, "label": intent.label, "status": intent.status})
    items.append({"kind": "asset", "ref": asset.ref, "label": asset.label, "status": asset.status})
    if asset.latest_decision is not None:
        items.append(_record("decision", asset.latest_decision))
    return items


def _forecast_evidence(ctx: AuthorizedAlignmentContext, grid: Grid) -> list[dict]:
    return [
        {
            "kind": "forecast",
            "ref": scenario_id(ctx, grid[cell]),
            "label": f"Illustrative: if transfer were to occur in year {cell[0]} ({PRESET_LABEL[cell[1]]})",
            "status": "illustrative",
        }
        for cell in _cells(grid)
    ]


def _rows(ctx: AuthorizedAlignmentContext, grid: Grid, year: int) -> list[dict]:
    """The eligible cells only: a transfer after the goal year has no probability to show (the engine's
    p=0.0 there would read as a measured shortfall). Evidence still cites every stored cell."""
    return [
        {
            "transfer_year": cell[0],
            "preset": cell[1],
            "p": grid[cell].p_cash_covers_goal,
            "cash_p50": grid[cell].cash_at_goal.p50,
            "value_p50": grid[cell].value_nominal[year].p50,
            "scenario_id": scenario_id(ctx, grid[cell]),
        }
        for cell in _eligible(grid, year)
    ]


@dataclass(frozen=True)
class _Model:
    """A context that reached the modeling step, with its grid."""

    ctx: AuthorizedAlignmentContext
    grid: Grid
    year: int
    amount: int
    threshold: float

    def evidence(self) -> list[dict]:
        return [
            *_estate_evidence(self.ctx),
            _goal_evidence(self.ctx),
            *_forecast_evidence(self.ctx, self.grid),
        ]

    def rows(self) -> list[dict]:
        return _rows(self.ctx, self.grid, self.year)

    def conditions(self) -> list[str]:
        source = (
            "the shared amount"
            if isinstance(self.ctx.goal, AdvisorGoalDetail)
            else "midpoint of the shared band"
        )
        return [
            HYPOTHETICAL_TIMING,
            INTENT_MAY_CHANGE,
            f"Goal modeled as ${self.amount:,} in today's dollars ({source}); taxes not modeled",
        ]

    def estate_known(self) -> list[str]:
        known = []
        if self.ctx.intent.instrument is not None:
            known.append(f"Estate intent verified: {self.ctx.intent.instrument.label}")
        if self.ctx.asset.restriction:
            known.append(f"Access restriction: {self.ctx.asset.restriction}")
        return known

    def assumptions(self) -> dict:
        any_result = next(iter(self.grid.values()))
        return {
            "goal_year": self.year,
            "goal_amount_today": self.amount,
            "amount_source": "amount_target"
            if isinstance(self.ctx.goal, AdvisorGoalDetail)
            else "amount_band_mid",
            "transfer_years": sorted({year for year, _ in self.grid}),
            "presets": [p for p in PRESETS if any(preset == p for _, preset in self.grid)],
            "review_threshold": self.threshold,
            "seed": any_result.seed,
            "model_version": any_result.model_version,
        }


def _draft(
    type_: InsightType, ctx: AuthorizedAlignmentContext, *, uses_intent: bool = True, **fields
) -> InsightDraft:
    """`uses_intent=False` keys the insight to the goal alone: it relies on no estate facts."""
    parts = (type_, ctx.intent.ref) if uses_intent else (type_,)
    fields.setdefault("headline_probability", None)
    fields.setdefault("scenario_rows", [])
    fields.setdefault("assumptions", {})
    return InsightDraft(
        type=type_,
        insight_key=":".join((*parts, ctx.goal_ref or "")),
        filter_tags=list(FILTER_TAGS[type_]),
        goal_ref=ctx.goal_ref,
        **fields,
    )


# --- Insights ----------------------------------------------------------------------------------


def _goal_only_opportunity(ctx: AuthorizedAlignmentContext) -> InsightDraft:
    """No verified intent: built from the shared goal alone, with no estate facts at all."""
    kind = _kind(ctx)
    return _draft(
        "relationship_opportunity",
        ctx,
        uses_intent=False,
        title=f"Planning conversation: shared {kind} goal",
        summary=(
            f"The heir shared a {kind} goal ({_bands(ctx)}). Offer an independent planning conversation "
            "about funding options and timing for their own goal."
        ),
        why_now="The heir chose to share this goal with you.",
        known=[f"Shared goal: {kind}, {_bands(ctx)}"],
        conditional=["Uses only what the heir chose to share"],
        contact=["Heir: offer a no-pressure planning conversation"],
        headline_condition="Based only on the goal the heir shared",
        evidence=[_goal_evidence(ctx)],
    )


def _legal_review(ctx: AuthorizedAlignmentContext) -> InsightDraft:
    asset = ctx.asset
    return _draft(
        "legal_review",
        ctx,
        title=f"Conflicting instruments: {asset.label}",
        summary=(
            f"Current verified instruments name different beneficiaries for {asset.label}. "
            "No forecast is shown until estate counsel resolves the conflict."
        ),
        why_now="A newly verified instrument conflicts with the intent on record for this interest.",
        known=[f"Intent on record: {ctx.intent.label}"],
        conditional=["The beneficiary of this interest is unresolved, so nothing is modeled"],
        contact=["Estate counsel: resolve the conflicting instruments", "Parent: confirm current intent"],
        headline_condition="Conflicting instruments — attorney review",
        evidence=[*_estate_evidence(ctx), _goal_evidence(ctx)],
    )


def _insufficient_data(ctx: AuthorizedAlignmentContext) -> InsightDraft:
    """No model was run: the goal lacks its timing or amount, or the asset lacks its valuation or a term."""
    missing = [
        name
        for name, value in (("timing", goal_year(ctx)), ("amount", goal_amount(ctx.goal)))
        if value is None
    ]
    kind, asset = _kind(ctx), ctx.asset
    known = [f"Shared goal: {kind}, {_bands(ctx)}"]
    if asset.missing_terms:
        known.append(f"Not recorded for {asset.label}: {', '.join(asset.missing_terms)}")
    if missing:
        summary = (
            f"The shared {kind} goal does not include its {' or '.join(missing)}, so no readiness model was run "
            "and no probability is shown. A planning conversation could clarify it."
        )
        known.append("Modeling needs both a goal year and an amount")
        contact = ["Heir: offer a planning conversation about timing and amount"]
        condition = INSUFFICIENT_DATA
    else:
        summary = (
            f"No {' or '.join(asset.missing_terms)} is recorded for {asset.label}, so no readiness model was run "
            f"and no probability is shown for the shared {kind} goal. Record the missing terms before any modeling."
        )
        contact = [
            "Parent: confirm the valuation and terms for this interest",
            f"Heir: offer a planning conversation about the {kind} goal",
        ]
        condition = INSUFFICIENT_TERMS
    return _draft(
        "relationship_opportunity",
        ctx,
        title=f"Planning conversation: shared {kind} goal",
        summary=summary,
        why_now="The heir chose to share this goal with you.",
        known=known,
        conditional=[],
        contact=contact,
        headline_condition=condition,
        evidence=[*_estate_evidence(ctx), _goal_evidence(ctx)],
    )


def _timing(m: _Model) -> list[InsightDraft]:
    ctx, kind = m.ctx, _kind(m.ctx)
    first = min(year for year, _ in m.grid)
    shared = {"scenario_rows": m.rows(), "evidence": m.evidence(), "assumptions": m.assumptions()}
    gap = _draft(
        "timing_gap",
        ctx,
        title="Goal timing precedes any modeled transfer",
        summary=(
            f"The shared {kind} goal (year {m.year}) comes before the earliest modeled transfer year ({first}). "
            "Treat it as an independent planning need, not an inheritance shortfall."
        ),
        why_now=f"The heir shared a {kind} goal ({_bands(ctx)}).",
        known=[
            f"Earliest modeled transfer: year {first} (illustrative)",
            f"Accessible cash from this interest in year {m.year} is zero in every modeled scenario",
        ],
        conditional=[HYPOTHETICAL_TIMING],
        contact=[f"Heir: offer an independent conversation about funding the {kind} goal"],
        headline_condition=(
            f"Goal in year {m.year} precedes the earliest modeled transfer (year {first}): independent planning need"
        ),
        **shared,
    )
    review = _draft(
        "timing_review",
        ctx,
        title="Review transfer-timing assumptions",
        summary=(
            f"No modeled transfer of {ctx.asset.label} falls before the shared goal in year {m.year}. Review the "
            "timing assumptions with the parent, and estate counsel if they wish; no transfer date is predicted."
        ),
        why_now=f"The current verified intent covers {ctx.intent.label}, and the shared goal comes first.",
        known=m.estate_known(),
        conditional=[HYPOTHETICAL_TIMING, INTENT_MAY_CHANGE],
        contact=["Parent: review timing assumptions", "Estate counsel, if the parent wishes"],
        headline_condition=f"No modeled transfer before year {first} (illustrative)",
        **shared,
    )
    return [gap, review]


def _liquidity_gap(m: _Model, cell: tuple[int, str]) -> InsightDraft:
    ctx, kind = m.ctx, _kind(m.ctx)
    year, preset = cell
    result, base = m.grid[cell], m.grid.get((year, "base"))
    known = []
    if base is not None and base.p_cash_covers_goal is not None:
        known.append(
            f"Base assumptions: {_pct(base.p_cash_covers_goal)} chance accessible cash covers the goal "
            f"if transfer were to occur in year {year} (illustrative)"
        )
        if preset != "base" and result.value_nominal[m.year].p50 == base.value_nominal[m.year].p50:
            known.append("Paper value is unchanged under this condition; only accessible cash moves")
    return _draft(
        "liquidity_gap",
        ctx,
        title=f"Conditional liquidity gap: {ctx.asset.label}",
        summary=(
            f"If transfer were to occur in year {year} {PRESET_CONDITION[preset]}, accessible cash from "
            f"{ctx.asset.label} would cover the shared {kind} goal in year {m.year} in only "
            f"{_pct(result.p_cash_covers_goal)} of illustrative paths. Review access terms and liquidity paths "
            "with the parent; nothing here changes the parent's own portfolio."
        ),
        why_now=f"The heir shared a {kind} goal ({_bands(ctx)}), and the current verified intent covers {ctx.intent.label}.",
        known=[*known, *m.estate_known()],
        conditional=m.conditions(),
        contact=[
            "Parent: review access terms and liquidity paths for this interest",
            "Estate counsel, if the parent wishes",
            "Heir: offer an independent planning conversation, without estate details",
        ],
        headline_probability=result.p_cash_covers_goal,
        headline_condition=_headline(m.year, cell),
        scenario_rows=m.rows(),
        evidence=m.evidence(),
        assumptions=m.assumptions(),
    )


def _unknown_terms(m: _Model) -> InsightDraft:
    ctx = m.ctx
    return _draft(
        "liquidity_gap",
        ctx,
        title=f"Access terms unknown: {ctx.asset.label}",
        summary=(
            f"Material access terms for {ctx.asset.label} are unknown, so no probability is shown for the shared "
            f"{_kind(ctx)} goal in year {m.year}. Attorney review of the access terms comes before any modeling."
        ),
        why_now=f"The heir shared a {_kind(ctx)} goal, and the current verified intent covers {ctx.intent.label}.",
        known=m.estate_known(),
        conditional=[UNKNOWN_TERMS_NOTE, HYPOTHETICAL_TIMING],
        contact=[
            "Estate counsel: confirm the sale and partner-consent terms",
            "Parent: review the access provisions",
        ],
        headline_condition=UNKNOWN_TERMS,
        scenario_rows=m.rows(),
        evidence=m.evidence(),
        assumptions=m.assumptions(),
    )


def _no_mismatch(m: _Model, probabilities: dict[tuple[int, str], float]) -> InsightDraft:
    ctx, kind = m.ctx, _kind(m.ctx)
    lowest = min(probabilities, key=lambda cell: (probabilities[cell], _order(cell)))
    p = probabilities[lowest]
    return _draft(
        "relationship_opportunity",
        ctx,
        title=f"No modeled mismatch: shared {kind} goal",
        summary=(
            f"Under these illustrative assumptions, accessible cash would cover the shared {kind} goal "
            f"({_bands(ctx)}) in at least {_pct(p)} of paths for every modeled transfer up to year {m.year}, "
            f"stress cases included. Offer a {kind} planning conversation."
        ),
        why_now=f"The heir shared a {kind} goal ({_bands(ctx)}).",
        known=[NO_MISMATCH, f"Lowest modeled chance: {_pct(p)} {_condition(*lowest)} (illustrative)"],
        conditional=m.conditions(),
        contact=[f"Heir: offer a {kind} planning conversation"],
        headline_probability=p,
        headline_condition=_headline(m.year, lowest),
        scenario_rows=m.rows(),
        evidence=m.evidence(),
        assumptions=m.assumptions(),
    )


def classify(ctx: AuthorizedAlignmentContext, grid: Grid | None, threshold: float) -> list[InsightDraft]:
    """Insight drafts for one pair, in blueprint precedence order. The first rule that applies decides."""
    if ctx.goal is None:
        return []  # unshared goal: nothing inferential exposed
    if ctx.intent is None or not ctx.intent.verified:
        return [_goal_only_opportunity(ctx)]
    if ctx.conflict:
        return [_legal_review(ctx)]
    inputs = model_inputs(ctx)
    if inputs is None:
        return [_insufficient_data(ctx)]
    if grid is None:
        raise ValueError("classify needs the forecast grid once the goal can be modeled")
    m = _Model(ctx, grid, *inputs, threshold)

    eligible = _eligible(grid, m.year)
    if not eligible:
        return _timing(m)
    probabilities = {cell: grid[cell].p_cash_covers_goal for cell in eligible}
    known = {cell: p for cell, p in probabilities.items() if p is not None}
    below = {cell: p for cell, p in known.items() if p < threshold}
    if below:
        return [_liquidity_gap(m, min(below, key=lambda cell: (below[cell], _order(cell))))]
    if not known:
        return [_unknown_terms(m)]
    return [_no_mismatch(m, known)]
