"""Sensitivity / scenario engine: premium×synergies + consideration-mix grids
and breakeven synergies for the merger model."""

from __future__ import annotations

from src.scenarios.engine import (
    breakeven_synergies,
    build_sensitivities,
    consideration_mix_grid,
    premium_x_synergies_grid,
)

__all__ = [
    "breakeven_synergies",
    "build_sensitivities",
    "consideration_mix_grid",
    "premium_x_synergies_grid",
]
