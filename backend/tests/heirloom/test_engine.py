import dataclasses
import time

import pytest

from app.heirloom.simulation.engine import (
    MODEL_VERSION,
    SALE_AFTER_HORIZON_NOTE,
    AssetTerms,
    ScenarioInput,
    run_grid,
    run_scenario,
)
from app.heirloom.simulation.scenarios import PRESETS, apply_preset

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


def make_input(terms=LLC, transfer_year=10, goal_year=12, **kw) -> ScenarioInput:
    return ScenarioInput(
        terms=terms,
        transfer_year=transfer_year,
        goal_year=goal_year,
        goal_amount_today=500_000,
        **kw,
    )


def test_fixed_seed_reproducible():
    a = run_scenario(make_input())
    b = run_scenario(make_input())
    assert a.cash_at_goal == b.cash_at_goal
    assert a.value_nominal == b.value_nominal
    assert a.input_hash == b.input_hash
    assert a.seed == 40626
    assert a.model_version == MODEL_VERSION == "relay-forecast-1.0"
    assert run_scenario(make_input(seed=1)).input_hash != a.input_hash


def test_quantiles_ordered():
    r = run_scenario(make_input())
    for series in (r.value_nominal, r.value_real, r.cash_by_year):
        assert len(series) == 31
        for q in series:
            assert q.p10 <= q.p50 <= q.p90
    assert r.cash_at_goal.p10 <= r.cash_at_goal.p50 <= r.cash_at_goal.p90


def test_zero_cash_before_transfer():
    r = run_scenario(make_input())
    for g in range(10):
        assert r.cash_by_year[g].year == g
        assert r.cash_by_year[g].p90 == 0
    assert r.cash_by_year[12].p90 > 0


def test_transfer_after_goal_is_zero_and_flagged():
    r = run_scenario(make_input(transfer_year=20, goal_year=12))
    assert r.transfer_after_goal is True
    assert r.cash_at_goal.p90 == 0
    assert run_scenario(make_input()).transfer_after_goal is False


def test_delay_changes_cash_not_value():
    base = run_scenario(make_input())
    delayed = run_scenario(make_input(preset="exit_delay_24m"))
    assert base.value_nominal == delayed.value_nominal
    assert base.cash_at_goal.p50 > delayed.cash_at_goal.p50
    assert base.sale_completion_year == 12
    assert delayed.sale_completion_year == 14


def test_debt_and_costs_subtracted_once():
    terms = dataclasses.replace(
        LLC,
        starting_value=5_000_000,
        attributable_debt=1_000_000,
        annual_volatility=0.0,
        expected_return=0.0,
        distribution_yield=0.0,
        admin_cost_fraction=0.0,
        liquidatable_fraction=1.0,
        sale_cost_fraction=0.1,
        sale_delay_years=0,
        admin_delay_years=0,
    )
    r = run_scenario(make_input(terms=terms, transfer_year=10, goal_year=10))
    assert r.cash_at_goal.p50 == pytest.approx(3_600_000)


def test_inflation_conversion():
    r = run_scenario(make_input())
    assert r.goal_nominal == pytest.approx(500_000 * 1.025**12)
    assert r.value_real[0].p50 == r.value_nominal[0].p50
    assert r.value_real[10].p50 == pytest.approx(r.value_nominal[10].p50 / 1.025**10)


def test_cash_never_negative():
    terms = dataclasses.replace(LLC, admin_cost_fraction=0.9, attributable_debt=10_000_000)
    r = run_scenario(make_input(terms=terms))
    for q in [*r.cash_by_year, r.cash_at_goal]:
        assert q.p10 >= 0 and q.p50 >= 0 and q.p90 >= 0


def test_stress_lowers_liquidity():
    base = run_scenario(make_input())
    for preset in ("shock_30_y1", "sale_haircut_20"):
        stressed = run_scenario(make_input(preset=preset))
        assert stressed.p_cash_covers_goal <= base.p_cash_covers_goal
        assert stressed.cash_at_goal.p50 < base.cash_at_goal.p50


def test_apply_preset():
    assert apply_preset(LLC, "base") == (LLC, 1.0)
    delayed, mult = apply_preset(LLC, "exit_delay_24m")
    assert delayed.sale_delay_years == 4 and mult == 1.0
    shocked, mult = apply_preset(LLC, "shock_30_y1")
    assert shocked == LLC and mult == 0.70
    haircut, mult = apply_preset(LLC, "sale_haircut_20")
    assert haircut.sale_cost_fraction == pytest.approx(0.29) and mult == 1.0


def test_unknown_terms_give_none():
    note = "Material access terms unknown — attorney review required"
    for terms in (
        dataclasses.replace(LLC, liquidatable_fraction=None),
        dataclasses.replace(LLC, sale_delay_years=None),
        dataclasses.replace(LLC, partner_consent_process_documented=False),
    ):
        r = run_scenario(make_input(terms=terms))
        assert r.p_cash_covers_goal is None
        assert r.shortfall_share is None
        assert note in r.limitations
    known = run_scenario(make_input())
    assert note not in known.limitations
    assert {
        "Illustrative assumptions; not a prediction",
        "Taxes not modeled",
        "Hypothetical transfer timing; no mortality modeled",
    } <= set(known.limitations)


def test_no_consent_requirement_means_documentation_not_needed():
    terms = dataclasses.replace(
        LLC, partner_consent_required=False, partner_consent_process_documented=False
    )
    assert run_scenario(make_input(terms=terms)).p_cash_covers_goal is not None


def test_golden_story():
    base = run_scenario(make_input())
    delayed = run_scenario(make_input(preset="exit_delay_24m"))
    assert base.p_cash_covers_goal >= 0.70
    assert delayed.p_cash_covers_goal <= 0.15
    assert base.shortfall_share == pytest.approx(1 - base.p_cash_covers_goal)
    assert base.admin_cost_at_transfer_p50 > 0


def test_grid_shape():
    t0 = time.perf_counter()
    grid = run_grid(make_input())
    elapsed = time.perf_counter() - t0
    assert len(grid) == 12
    assert set(grid) == {(t, p) for t in (10, 20, 30) for p in PRESETS}
    assert grid[(20, "base")].transfer_after_goal is True
    assert elapsed < 0.5


def test_sale_after_horizon_is_flagged_not_silent():
    res = run_scenario(make_input(transfer_year=30, goal_year=30))
    assert res.sale_completion_year is None
    assert SALE_AFTER_HORIZON_NOTE in res.limitations
    grid = run_grid(make_input(goal_year=30))
    assert SALE_AFTER_HORIZON_NOTE in grid[(30, "base")].limitations
    assert SALE_AFTER_HORIZON_NOTE not in grid[(10, "base")].limitations


def test_sale_within_horizon_has_no_horizon_note():
    res = run_scenario(make_input())
    assert res.sale_completion_year == 12
    assert SALE_AFTER_HORIZON_NOTE not in res.limitations
