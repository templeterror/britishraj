import dataclasses

from app.heirloom.dto.advisor import AdvisorGoalDetail, AdvisorGoalSummary
from app.heirloom.services.classifier import (
    AssetFacts,
    AuthorizedAlignmentContext,
    IntentFacts,
    RecordFacts,
    classify,
    model_inputs,
)
from app.heirloom.simulation.engine import AssetTerms, ScenarioInput, run_grid

THRESHOLD = 0.5
FORBIDDEN_IN_RELATIONSHIP_COPY = ("llc", "intend", "estate", "inherit")

# Literal copy of the asset-family-llc fixture terms (Morgan Family Holdings LLC).
LLC = AssetTerms(
    starting_value=5_000_000,
    attributable_debt=1_200_000,
    expected_return=0.055,
    annual_volatility=0.22,
    annual_fee=0.0,
    liquidatable_fraction=0.25,
    sale_delay_years=2,
    admin_delay_years=0,
    sale_cost_fraction=0.09,
    distribution_yield=0.01,
    admin_cost_fraction=0.01,
    partner_consent_required=True,
    partner_consent_process_documented=True,
)
INSTRUMENT = RecordFacts("instr-estate-letter-2026", "Estate planning letter, 2026", "verified")
INTENT = IntentFacts(
    ref="intent-james-llc",
    label="Robert's 40% membership interest",
    status="verified",
    verified=True,
    instrument=INSTRUMENT,
)
ASSET = AssetFacts(
    ref="asset-family-llc",
    label="40% interest, Morgan Family Holdings LLC",
    status="verified",
    terms=LLC,
    restriction="Partner consent required; 25% liquidatable",
    latest_decision=None,
)


def summary_goal(horizon_max: int | None = 12, amount_mid: int | None = 500_000, kind: str = "business"):
    return AdvisorGoalSummary(
        goal_id="00000000-0000-0000-0000-000000000001",
        kind=kind,
        horizon_band="8–12 years" if horizon_max == 12 else "timing not set",
        amount_band="about $500K" if amount_mid else "amount not set",
        amount_band_mid=amount_mid,
        horizon_max_years=horizon_max,
    )


def detail_goal(target_year: int | None, amount: int | None, horizon_max: int | None = None):
    return AdvisorGoalDetail(
        **summary_goal(horizon_max, amount).model_dump(),
        amount_target=amount,
        target_year=target_year,
        milestone=None,
        description="Build a software company.",
    )


def context(
    goal=None, intent=INTENT, asset=ASSET, conflict=False, decision=None
) -> AuthorizedAlignmentContext:
    if asset is not None and decision is not None:
        asset = dataclasses.replace(asset, latest_decision=decision)
    return AuthorizedAlignmentContext(
        family_ref="demo-morgan",
        as_of_year=2026,
        intent=intent,
        conflict=conflict,
        asset=asset,
        goal=goal,
        decision_refs=[decision.ref] if decision else [],
        consent_revision=1,
        goal_ref="goal-james-business" if goal else None,
    )


def grid(goal_year: int, amount: float, terms: AssetTerms = LLC):
    """The real scenario grid, built the way the readiness pipeline builds it."""
    base = ScenarioInput(
        terms=terms,
        transfer_year=10,
        goal_year=goal_year,
        goal_amount_today=amount,
        horizon_years=max(30, goal_year),
    )
    return run_grid(base)


def _texts(draft) -> str:
    return " ".join(
        [draft.title, draft.summary, draft.why_now, draft.headline_condition, *draft.known]
    ).lower()


def test_no_goal_no_insights():
    assert classify(context(goal=None), None, THRESHOLD) == []
    assert classify(context(goal=None, intent=None, asset=None), None, THRESHOLD) == []


def test_unverified_intent_relationship_only():
    unverified = dataclasses.replace(INTENT, status="proposed", verified=False)
    for ctx in (
        context(summary_goal(), intent=None, asset=None),
        context(summary_goal(), intent=unverified),
    ):
        (draft,) = classify(ctx, grid(12, 500_000), THRESHOLD)
        assert draft.type == "relationship_opportunity"
        assert draft.filter_tags == ["heir_conversation"]
        assert draft.headline_probability is None
        assert draft.scenario_rows == []
        assert [e["kind"] for e in draft.evidence] == ["goal"]
        assert draft.goal_ref == "goal-james-business"
        for word in FORBIDDEN_IN_RELATIONSHIP_COPY:
            assert word not in draft.summary.lower(), word
            assert word not in _texts(draft), word
        assert "business" in draft.summary
        assert "about $500K" in draft.summary


def test_conflict_legal_review():
    contested = dataclasses.replace(INTENT, status="contested")
    (draft,) = classify(context(summary_goal(), intent=contested, conflict=True), None, THRESHOLD)
    assert draft.type == "legal_review"
    assert draft.filter_tags == ["legal_source_conflict"]
    assert draft.headline_probability is None
    assert draft.scenario_rows == []
    assert {"estate_instrument", "estate_intent", "asset", "goal"} <= {e["kind"] for e in draft.evidence}


def test_goal_before_earliest_transfer_is_timing():
    drafts = classify(context(summary_goal(horizon_max=3)), grid(3, 500_000), THRESHOLD)
    assert [d.type for d in drafts] == ["timing_gap", "timing_review"]
    gap, review = drafts
    assert gap.filter_tags == ["heir_conversation", "scenario_mismatch"]
    assert review.filter_tags == ["needs_parent_review"]
    for draft in drafts:
        assert draft.headline_probability is None  # never a 0% "shortfall" for a timing question
        assert "year 10" in draft.headline_condition
        assert draft.scenario_rows == []  # every modeled transfer falls after the goal: nothing to quote
        assert "forecast" in {e["kind"] for e in draft.evidence}
    assert "independent" in gap.summary.lower()


def test_golden_liquidity_gap_names_exit_delay():
    results = grid(12, 500_000)
    base_p = results[(10, "base")].p_cash_covers_goal
    assert base_p >= 0.70

    (draft,) = classify(context(summary_goal(horizon_max=12)), results, THRESHOLD)
    assert draft.type == "liquidity_gap"
    assert draft.filter_tags == ["needs_parent_review", "scenario_mismatch"]
    assert draft.headline_probability <= 0.15
    assert draft.headline_probability == results[(10, "exit_delay_24m")].p_cash_covers_goal
    assert "24 months" in draft.headline_condition
    assert "if transfer were to occur in year 10" in draft.headline_condition
    assert "illustrative" in draft.headline_condition
    assert any(f"{base_p:.0%}" in line for line in draft.known)
    assert draft.goal_ref == "goal-james-business"
    assert draft.insight_key == "liquidity_gap:intent-james-llc:goal-james-business"

    rows = {(r["transfer_year"], r["preset"]): r for r in draft.scenario_rows}
    assert set(rows) == {cell for cell in results if cell[0] <= 12}  # years 20 and 30 come after the goal
    assert rows[(10, "base")]["p"] == base_p
    assert (
        rows[(10, "base")]["value_p50"] == rows[(10, "exit_delay_24m")]["value_p50"]
    )  # delay moves cash only
    assert len({r["scenario_id"] for r in draft.scenario_rows}) == 4

    kinds = [e["kind"] for e in draft.evidence]
    assert {"estate_instrument", "estate_intent", "asset", "goal", "forecast"} <= set(kinds)
    assert "decision" not in kinds
    forecast_refs = {e["ref"] for e in draft.evidence if e["kind"] == "forecast"}
    assert len(forecast_refs) == 12  # every stored cell is cited
    assert {r["scenario_id"] for r in draft.scenario_rows} <= forecast_refs
    assert draft.assumptions["goal_year"] == 12
    assert draft.assumptions["goal_amount_today"] == 500_000


def test_liquidity_gap_cites_latest_verified_decision():
    decision = RecordFacts(
        "decision-retain-llc", "Keep the family LLC interest rather than force a sale", "verified"
    )
    (draft,) = classify(context(summary_goal(), decision=decision), grid(12, 500_000), THRESHOLD)
    assert {
        "ref": decision.ref,
        "kind": "decision",
        "label": decision.label,
        "status": "verified",
    } in draft.evidence


def test_foundation_no_mismatch():
    goal = summary_goal(horizon_max=25, amount_mid=250_000, kind="philanthropy")
    (draft,) = classify(context(goal), grid(25, 250_000), THRESHOLD)
    assert draft.type == "relationship_opportunity"
    assert draft.filter_tags == ["heir_conversation"]
    assert "No modeled mismatch under these assumptions" in draft.known
    assert draft.headline_probability >= THRESHOLD


def test_missing_timing_is_insufficient_data():
    insufficient = "Insufficient modeling data: goal timing or amount not shared"
    for goal in (
        summary_goal(horizon_max=None),
        detail_goal(target_year=None, amount=500_000),
        summary_goal(horizon_max=12, amount_mid=None),
        detail_goal(target_year=2038, amount=None),
    ):
        (draft,) = classify(context(goal), None, THRESHOLD)
        assert draft.type == "relationship_opportunity"
        assert draft.headline_probability is None
        assert draft.headline_condition == insufficient
        assert draft.scenario_rows == []

    # A shared detail without a horizon falls back to target_year - as_of_year (2038 - 2026 = 12).
    (draft,) = classify(context(detail_goal(target_year=2038, amount=500_000)), grid(12, 500_000), THRESHOLD)
    assert draft.type == "liquidity_gap"
    assert draft.assumptions["goal_year"] == 12


def test_unknown_terms_no_reassuring_number():
    unknown = dataclasses.replace(LLC, liquidatable_fraction=None)
    asset = dataclasses.replace(ASSET, terms=unknown)
    (draft,) = classify(context(summary_goal(), asset=asset), grid(12, 500_000, unknown), THRESHOLD)
    assert draft.type == "liquidity_gap"
    assert draft.headline_probability is None
    assert draft.headline_condition == "Access terms unknown — attorney review"
    assert all(row["p"] is None for row in draft.scenario_rows)
    assert "%" not in draft.headline_condition
    assert "of illustrative paths" not in draft.summary


def test_transfer_after_goal_rows_carry_no_probability():
    """A transfer after the goal year cannot fund it: that is a timing question, never a measured 0%."""
    cases = [
        (summary_goal(horizon_max=12), grid(12, 500_000)),
        (summary_goal(horizon_max=3), grid(3, 500_000)),
        (summary_goal(horizon_max=25, amount_mid=250_000, kind="philanthropy"), grid(25, 250_000)),
    ]
    for goal, results in cases:
        assert any(r.transfer_after_goal and r.p_cash_covers_goal == 0.0 for r in results.values())
        for draft in classify(context(goal), results, THRESHOLD):
            rows = draft.scenario_rows
            assert all(row["transfer_year"] <= goal.horizon_max_years for row in rows), draft.type
            assert not any(row["p"] == 0.0 for row in rows), draft.type


def test_unrecorded_asset_terms_are_insufficient_data():
    """A missing valuation or modeling term is unknown, not zero: no grid, no probability."""
    unrecorded = dataclasses.replace(ASSET, terms=None, missing_terms=("estimated value",))
    ctx = context(summary_goal(), asset=unrecorded)
    assert model_inputs(ctx) is None  # so the pipeline runs no grid
    (draft,) = classify(ctx, None, THRESHOLD)
    assert draft.type == "relationship_opportunity"
    assert draft.headline_probability is None
    assert draft.headline_condition == "Insufficient modeling data: asset valuation or terms not recorded"
    assert draft.scenario_rows == []
    assert "forecast" not in {e["kind"] for e in draft.evidence}
    assert "estimated value" in draft.summary
    assert "of illustrative paths" not in draft.summary

    # A goal that is missing its timing too keeps the goal's insufficient-data condition.
    (draft,) = classify(context(summary_goal(horizon_max=None), asset=unrecorded), None, THRESHOLD)
    assert draft.headline_condition == "Insufficient modeling data: goal timing or amount not shared"
    assert draft.headline_probability is None
    assert any("estimated value" in line for line in draft.known)
