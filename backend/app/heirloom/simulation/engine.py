"""Seeded, transfer-aware Monte Carlo forecast of an illiquid asset's value and accessible cash.

All outputs are illustrative: they describe what would happen *if* a transfer occurred in a given
year, not a prediction.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from dataclasses import dataclass

import numpy as np

from app.heirloom.simulation.scenarios import PRESETS, StressPreset, apply_preset

MODEL_VERSION = "relay-forecast-1.0"
UNKNOWN_TERMS_NOTE = "Material access terms unknown — attorney review required"
BASE_LIMITATIONS = (
    "Illustrative assumptions; not a prediction",
    "Taxes not modeled",
    "Hypothetical transfer timing; no mortality modeled",
)


@dataclass(frozen=True)
class AssetTerms:
    starting_value: float
    attributable_debt: float
    expected_return: float
    annual_volatility: float
    annual_fee: float
    liquidatable_fraction: float | None
    sale_delay_years: int | None
    admin_delay_years: int
    sale_cost_fraction: float
    distribution_yield: float
    admin_cost_fraction: float
    partner_consent_required: bool
    partner_consent_process_documented: bool


@dataclass(frozen=True)
class ScenarioInput:
    terms: AssetTerms
    transfer_year: int
    goal_year: int
    goal_amount_today: float
    inflation_rate: float = 0.025
    horizon_years: int = 30
    paths: int = 2000
    seed: int = 40626
    preset: StressPreset = "base"


@dataclass(frozen=True)
class YearQuantiles:
    year: int
    p10: float
    p50: float
    p90: float


@dataclass(frozen=True)
class ScenarioResult:
    value_nominal: list[YearQuantiles]
    value_real: list[YearQuantiles]
    cash_by_year: list[YearQuantiles]
    cash_at_goal: YearQuantiles
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


def input_hash(inp: ScenarioInput) -> str:
    payload = {"model_version": MODEL_VERSION, "input": dataclasses.asdict(inp)}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _quantiles(year: int, x: np.ndarray) -> YearQuantiles:
    p10, p50, p90 = np.percentile(x, [10, 50, 90], method="linear")
    return YearQuantiles(year, float(p10), float(p50), float(p90))


def _terms_unknown(t: AssetTerms) -> bool:
    return (
        t.liquidatable_fraction is None
        or t.sale_delay_years is None
        or (t.partner_consent_required and not t.partner_consent_process_documented)
    )


def _validate(inp: ScenarioInput) -> None:
    if inp.horizon_years < 1 or inp.paths < 1:
        raise ValueError("horizon_years and paths must be positive")
    if not 0 <= inp.transfer_year <= inp.horizon_years:
        raise ValueError("transfer_year must lie within the horizon")
    if not 0 <= inp.goal_year <= inp.horizon_years:
        raise ValueError("goal_year must lie within the horizon")


def run_scenario(inp: ScenarioInput) -> ScenarioResult:
    _validate(inp)
    terms, shock = apply_preset(inp.terms, inp.preset)
    horizon, T = inp.horizon_years, inp.transfer_year
    unknown = _terms_unknown(terms)

    # Paper value paths: lognormal with fee-adjusted drift; the year-1 shock is permanent.
    rng = np.random.Generator(np.random.PCG64(inp.seed))
    z = rng.standard_normal((inp.paths, horizon))
    sigma = terms.annual_volatility
    drift = math.log(1 + terms.expected_return - terms.annual_fee) - 0.5 * sigma**2
    growth = np.exp(drift + sigma * z)
    v = np.empty((inp.paths, horizon + 1))
    v[:, 0] = terms.starting_value
    v[:, 1:] = terms.starting_value * np.cumprod(growth, axis=1)
    v[:, 1:] *= shock
    years = np.arange(horizon + 1)
    real = v / (1 + inp.inflation_rate) ** years

    # Accessible cash if the interest passed to the heir in year T, by each possible goal year G.
    admin_cost = terms.admin_cost_fraction * v[:, T]
    dist_cum = np.cumsum(terms.distribution_yield * v[:, T:], axis=1)  # column k => G = T + k
    sale_year = None
    sale = np.zeros(inp.paths)
    if not unknown:
        sale_year = T + terms.admin_delay_years + terms.sale_delay_years
        if sale_year <= horizon:
            sale = (
                terms.liquidatable_fraction
                * np.maximum(0.0, v[:, sale_year] - terms.attributable_debt)
                * (1 - terms.sale_cost_fraction)
            )
        else:
            sale_year = None

    zeros = np.zeros(inp.paths)
    cash = []
    for g in range(horizon + 1):
        if T > g:
            cash.append(zeros)
            continue
        paid_sale = sale if sale_year is not None and sale_year <= g else zeros
        cash.append(np.maximum(0.0, paid_sale + dist_cum[:, g - T] - admin_cost))

    goal_nominal = inp.goal_amount_today * (1 + inp.inflation_rate) ** inp.goal_year
    cash_goal = cash[inp.goal_year]
    p_cover = None if unknown else float(np.mean(cash_goal >= goal_nominal))

    limitations = list(BASE_LIMITATIONS)
    if unknown:
        limitations.append(UNKNOWN_TERMS_NOTE)

    return ScenarioResult(
        value_nominal=[_quantiles(t, v[:, t]) for t in range(horizon + 1)],
        value_real=[_quantiles(t, real[:, t]) for t in range(horizon + 1)],
        cash_by_year=[_quantiles(g, c) for g, c in enumerate(cash)],
        cash_at_goal=_quantiles(inp.goal_year, cash_goal),
        goal_nominal=goal_nominal,
        p_cash_covers_goal=p_cover,
        shortfall_share=None if p_cover is None else 1.0 - p_cover,
        sale_completion_year=sale_year,
        transfer_after_goal=T > inp.goal_year,
        admin_cost_at_transfer_p50=float(np.median(admin_cost)),
        limitations=limitations,
        seed=inp.seed,
        model_version=MODEL_VERSION,
        input_hash=input_hash(inp),
    )


def run_grid(
    base: ScenarioInput,
    transfer_years: tuple[int, ...] = (10, 20, 30),
    presets: tuple[str, ...] = PRESETS,
) -> dict[tuple[int, str], ScenarioResult]:
    return {
        (t, p): run_scenario(dataclasses.replace(base, transfer_year=t, preset=p))
        for t in transfer_years
        for p in presets
    }
