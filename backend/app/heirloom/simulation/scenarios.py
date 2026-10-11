"""Stress presets applied to asset terms before a forecast run."""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Literal, get_args

if TYPE_CHECKING:
    from app.heirloom.simulation.engine import AssetTerms

StressPreset = Literal["base", "exit_delay_24m", "shock_30_y1", "sale_haircut_20"]
PRESETS: tuple[str, ...] = get_args(StressPreset)

EXIT_DELAY_YEARS = 2
YEAR1_SHOCK_MULTIPLIER = 0.70
SALE_HAIRCUT = 0.20


def apply_preset(terms: AssetTerms, preset: StressPreset) -> tuple[AssetTerms, float]:
    """Return (adjusted terms, multiplier applied to year-1 value)."""
    if preset == "base":
        return terms, 1.0
    if preset == "exit_delay_24m":
        if terms.sale_delay_years is None:
            return terms, 1.0
        return dataclasses.replace(terms, sale_delay_years=terms.sale_delay_years + EXIT_DELAY_YEARS), 1.0
    if preset == "shock_30_y1":
        return terms, YEAR1_SHOCK_MULTIPLIER
    if preset == "sale_haircut_20":
        return dataclasses.replace(terms, sale_cost_fraction=terms.sale_cost_fraction + SALE_HAIRCUT), 1.0
    raise ValueError(f"unknown stress preset: {preset}")
