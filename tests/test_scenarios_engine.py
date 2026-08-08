"""Tests for the sensitivity / scenario engine.

The gate is MONOTONICITY: the premium×synergies grid must be non-increasing in
premium (more premium ⇒ more dilutive) and non-decreasing in synergies (more
synergies ⇒ more accretive). We also check breakeven-synergy consistency (plug
it back, Year-N A/D ≈ 0, and it brackets the grid's sign change) and a
real-deal smoke test that prints the grid + breakeven for the orchestrator.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import pytest
from src.combine import CombinationEngine
from src.deal import DealEngineImpl
from src.flagship import build_flagship_bundle
from src.interfaces import DealAssumptions, StatementSet
from src.scenarios import (
    breakeven_synergies,
    build_sensitivities,
    consideration_mix_grid,
    premium_x_synergies_grid,
)
from src.scenarios.engine import _accretion_dilution
from src.schema import (
    ConsiderationType,
    DealTerms,
    DocProvenance,
    LineItem,
    Period,
    PeriodType,
    SourcedValue,
)

_PRECEDENTS_CSV = "data/curated/precedents_software.csv"


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def bundle():
    return build_flagship_bundle(_PRECEDENTS_CSV)


@pytest.fixture(scope="module")
def sens(bundle):
    return build_sensitivities(bundle)


def _grid_common(bundle):
    tgt = bundle.target_statements
    proj0 = tgt.n_hist
    return {
        "target_book_equity": float(tgt.series(LineItem.TOTAL_EQUITY)[proj0] or 0.0),
        "target_existing_goodwill": float(tgt.series(LineItem.GOODWILL)[proj0] or 0.0),
    }


# --------------------------------------------------------------------------- #
# Monotonicity — the DoD gate
# --------------------------------------------------------------------------- #
def test_premium_x_synergies_monotone(sens):
    g = sens.premium_x_synergies
    # Every row: non-decreasing across synergies (more synergies ⇒ more accretive).
    for row in g.values:
        for j in range(1, len(row)):
            assert row[j] >= row[j - 1] - 1e-9, "A/D must rise with synergies"
    # Every column: non-increasing down premiums (more premium ⇒ more dilutive).
    for j in range(len(g.col_values)):
        col = [g.values[i][j] for i in range(len(g.row_values))]
        for i in range(1, len(col)):
            assert col[i] <= col[i - 1] + 1e-9, "A/D must fall with premium"


def test_premium_x_synergies_shape(sens):
    g = sens.premium_x_synergies
    assert g.row_label == "premium"
    assert g.col_label == "synergies"
    assert len(g.values) == len(g.row_values)
    assert all(len(r) == len(g.col_values) for r in g.values)
    assert g.year_idx == 0


def test_consideration_mix_monotone(sens):
    """Measured direction for THIS deal (expensive target, ~5% debt): more cash
    ⇒ more debt-funded interest ⇒ MORE dilutive at zero synergies. Synergy axis
    is still non-decreasing. See consideration_mix_grid docstring."""
    m = sens.consideration_mix
    assert m.row_label == "cash_fraction"
    # Synergy axis: non-decreasing across each row.
    for row in m.values:
        for j in range(1, len(row)):
            assert row[j] >= row[j - 1] - 1e-9
    # Cash-fraction axis at zero synergies (first column): non-increasing —
    # more cash is more dilutive when the interest cost dominates.
    first_col = [m.values[i][0] for i in range(len(m.row_values))]
    for i in range(1, len(first_col)):
        assert first_col[i] <= first_col[i - 1] + 1e-9, "more cash ⇒ more dilutive here"


# --------------------------------------------------------------------------- #
# Breakeven consistency
# --------------------------------------------------------------------------- #
def test_breakeven_zeroes_accretion(bundle, sens):
    """Plug the breakeven run-rate back through the engine at the base structure;
    Year-0 A/D must be ≈ 0."""
    be = sens.breakeven_synergies
    assert be is not None and be > 0.0
    terms = bundle.terms
    ad = _accretion_dilution(
        terms,
        bundle.deal_assumptions,
        bundle.acquirer_statements,
        bundle.target_statements,
        cash_per_share=terms.cash_per_share.value,
        exchange_ratio=terms.exchange_ratio.value,
        synergy_run_rate=be,
        year_idx=0,
        deal_engine=DealEngineImpl(),
        combine_engine=CombinationEngine(),
        **_grid_common(bundle),
    )
    assert ad == pytest.approx(0.0, abs=1e-6)


def test_breakeven_brackets_grid_sign_change(sens):
    """Breakeven must sit between the synergy columns that bracket A/D = 0 in the
    base-premium row (premium closest to the disclosed ~0.30)."""
    be = sens.breakeven_synergies
    g = sens.premium_x_synergies
    i = min(range(len(g.row_values)), key=lambda k: abs(g.row_values[k] - 0.30))
    row = g.values[i]
    # find the bracket where sign flips from negative to positive
    j = next(k for k in range(1, len(row)) if row[k - 1] < 0.0 <= row[k])
    assert g.col_values[j - 1] <= be <= g.col_values[j]


# --------------------------------------------------------------------------- #
# Hand-built synthetic bundle — exercises edge branches deterministically
# --------------------------------------------------------------------------- #
def _prov() -> DocProvenance:
    return DocProvenance(
        accession="0000000000-00-000000", form="8-K", filed=date(2024, 1, 1), section="test"
    )


def _sv(value: float, unit: str) -> SourcedValue:
    return SourcedValue(value=value, provenance=_prov(), unit=unit, label="test")


def _synthetic_terms(cash: float = 20.0, xratio: float = 0.5) -> DealTerms:
    return DealTerms(
        acquirer_ticker="ACQ",
        target_ticker="TGT",
        acquirer_name="Acq",
        target_name="Tgt",
        announce_date=date(2024, 1, 1),
        close_date=None,
        consideration_type=ConsiderationType.MIXED,
        cash_per_share=_sv(cash, "USD/share"),
        exchange_ratio=_sv(xratio, "ratio"),
        reference_acquirer_price=_sv(50.0, "USD/share"),
        premium_reference_price=_sv(40.0, "USD/share"),
        target_shares_outstanding=_sv(1_000_000.0, "shares"),
    )


def _flat_statements(net_income: float, shares: float) -> StatementSet:
    periods = [
        Period(ptype=PeriodType.DURATION, start=date(2024, 1, 1), end=date(2024, 12, 31), fp="FY"),
        Period(ptype=PeriodType.DURATION, start=date(2025, 1, 1), end=date(2025, 12, 31), fp="FY"),
        Period(ptype=PeriodType.DURATION, start=date(2026, 1, 1), end=date(2026, 12, 31), fp="FY"),
    ]
    rows = {
        LineItem.NET_INCOME: [net_income] * 3,
        LineItem.SHARES_DILUTED: [shares] * 3,
        LineItem.OPERATING_INCOME: [net_income] * 3,
        LineItem.REVENUE: [net_income * 5] * 3,
        LineItem.DEP_AMORT: [0.0] * 3,
        LineItem.PRETAX_INCOME: [net_income] * 3,
        LineItem.INCOME_TAX_EXPENSE: [0.0] * 3,
    }
    return StatementSet(periods=periods, rows=rows, n_hist=1)


def _synthetic_da() -> DealAssumptions:
    return DealAssumptions(
        new_debt=0.0,
        new_debt_rate=0.05,
        cash_on_hand_used=5_000_000.0,
        foregone_cash_yield=0.03,
        advisory_fees=0.0,
        financing_fees=0.0,
        intangible_step_up=0.0,
        intangible_useful_life_years=0.0,
        deferred_tax_rate=0.21,
        marginal_tax_rate=0.21,
        new_shares_issued=0.0,
    )


def test_synthetic_grid_monotone():
    terms = _synthetic_terms()
    acq = _flat_statements(net_income=10_000_000.0, shares=2_000_000.0)
    tgt = _flat_statements(net_income=3_000_000.0, shares=1_000_000.0)
    g = premium_x_synergies_grid(
        terms,
        _synthetic_da(),
        acq,
        tgt,
        year_idx=0,
        target_book_equity=5_000_000.0,
        target_existing_goodwill=1_000_000.0,
    )
    for row in g.values:
        for j in range(1, len(row)):
            assert row[j] >= row[j - 1] - 1e-9
    for j in range(len(g.col_values)):
        col = [g.values[i][j] for i in range(len(g.row_values))]
        for i in range(1, len(col)):
            assert col[i] <= col[i - 1] + 1e-9


def test_synthetic_mix_grid_and_breakeven():
    terms = _synthetic_terms()
    acq = _flat_statements(net_income=10_000_000.0, shares=2_000_000.0)
    tgt = _flat_statements(net_income=3_000_000.0, shares=1_000_000.0)
    common = {"target_book_equity": 5_000_000.0, "target_existing_goodwill": 1_000_000.0}
    m = consideration_mix_grid(terms, _synthetic_da(), acq, tgt, year_idx=0, **common)
    assert len(m.values) == len(m.row_values)
    # Breakeven: this small deal may be accretive at zero synergies (all-stock-ish
    # and cheap) — either a positive root or None (unbracketed) is acceptable.
    be = breakeven_synergies(terms, _synthetic_da(), acq, tgt, year_idx=0, **common)
    assert be is None or be >= 0.0


def test_breakeven_none_when_already_accretive():
    """A deal accretive at zero synergies (no cash, no debt, cheap stock) has no
    positive breakeven ⇒ None."""
    terms = _synthetic_terms(cash=0.0, xratio=0.1)
    acq = _flat_statements(net_income=10_000_000.0, shares=2_000_000.0)
    tgt = _flat_statements(net_income=5_000_000.0, shares=1_000_000.0)
    be = breakeven_synergies(
        terms,
        _synthetic_da(),
        acq,
        tgt,
        year_idx=0,
        target_book_equity=5_000_000.0,
        target_existing_goodwill=1_000_000.0,
    )
    assert be is None


def test_missing_required_leg_raises():
    terms = _synthetic_terms()
    terms = replace(terms, cash_per_share=None)
    acq = _flat_statements(net_income=10_000_000.0, shares=2_000_000.0)
    tgt = _flat_statements(net_income=3_000_000.0, shares=1_000_000.0)
    with pytest.raises(ValueError, match="cash_per_share"):
        consideration_mix_grid(terms, _synthetic_da(), acq, tgt, year_idx=0)


# --------------------------------------------------------------------------- #
# Real-deal smoke test — prints the grid + breakeven for the orchestrator
# --------------------------------------------------------------------------- #
def test_real_deal_smoke(sens, capsys):
    g = sens.premium_x_synergies
    assert g.values and all(g.values)
    assert sens.consideration_mix.values
    with capsys.disabled():
        print("\n=== SNPS/ANSS premium × synergies — Year-1 accretion/(dilution) ===")
        header = "premium\\syn  " + "  ".join(f"{c / 1e9:6.1f}B" for c in g.col_values)
        print(header)
        for i, row in enumerate(g.values):
            cells = "  ".join(f"{v * 100:6.1f}%" for v in row)
            print(f"   {g.row_values[i] * 100:4.0f}%    {cells}")
        be = sens.breakeven_synergies
        print(f"Breakeven annual synergy run-rate (Year-1 A/D=0): ${be / 1e9:.2f}B")
