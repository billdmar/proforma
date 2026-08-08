"""Fairness-opinion differential tests.

Two layers:

* **Hand-built disclosure** — a small synthetic ``FairnessDisclosure`` whose
  implied ranges and overlap %s are hand-computed to the cent, exercising the
  DCF and equity-multiple reproduction paths and the overlap arithmetic.
* **Real deal** — ``run_flagship_fairness()`` reproduces Qatalyst Partners'
  three disclosed ANSYS methodologies; the per-methodology disclosed-vs-our
  ranges and overlaps are PRINTED (measured, never asserted to a threshold).

Self-contained: hand-built fixtures use only the frozen contracts + the built
valuation/comps engines, so the expected DCF numbers are re-derived by calling
``dcf_from_ufcf`` directly (the same primitive the engine uses), pinning the
rate/multiple PAIRING and the per-share bridge to the cent.
"""

from __future__ import annotations

from datetime import date

import pytest
from src.fairness import run_fairness_differential, run_flagship_fairness
from src.fairness.engine import _overlap_pct
from src.interfaces import StatementSet, TerminalAssumptions
from src.schema import (
    AdvisorMethodology,
    DocProvenance,
    FairnessDisclosure,
    LineItem,
    Period,
    PeriodType,
    SourcedRange,
    SourcedValue,
)
from src.valuation import dcf_from_ufcf

_MILLIONS = 1_000_000.0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _prov() -> DocProvenance:
    return DocProvenance(
        accession="0000000000-00-000000",
        form="DEFM14A",
        filed=date(2024, 1, 1),
        section="test",
        quote="synthetic fixture",
    )


def _range(low: float, high: float, unit: str = "USD/share") -> SourcedRange:
    return SourcedRange(low=low, high=high, provenance=_prov(), unit=unit)


def _empty_statements() -> StatementSet:
    """Minimal StatementSet — carried for symmetry; the engine reads the
    DISCLOSED projections, not these statements."""
    p = Period(PeriodType.INSTANT, end=date(2024, 12, 31))
    return StatementSet(periods=[p], rows={LineItem.REVENUE: [None]}, n_hist=1)


def _hand_disclosure() -> FairnessDisclosure:
    """A synthetic 3-methodology disclosure with round-number inputs.

    UFCF stream (Management Case 1): [100, 200] $M — a 1-year explicit horizon
    (100 $M) with a 200 $M terminal-year metric.
    """
    ufcf = [
        SourcedValue(value=100.0, provenance=_prov(), unit="USD millions"),
        SourcedValue(value=200.0, provenance=_prov(), unit="USD millions"),
    ]
    dcf = AdvisorMethodology(
        method="Discounted Cash Flow",
        implied_range=_range(50.0, 400.0),
        assumptions={
            "discount_rate": _range(10.0, 12.0, unit="percent"),
            "ntm_ufcf_multiple": _range(15.0, 25.0, unit="x"),
        },
    )
    selco = AdvisorMethodology(
        method="Selected Companies",
        implied_range=_range(150.0, 250.0),
        assumptions={"cy2024e_lfcf_multiple": _range(10.0, 20.0, unit="x")},
    )
    seltx = AdvisorMethodology(
        method="Selected Transactions",
        implied_range=_range(50.0, 90.0),
        assumptions={"ntm_lfcf_multiple": _range(10.0, 20.0, unit="x")},
    )
    return FairnessDisclosure(
        advisor="Test Advisor",
        represents="TGT",
        methodologies=[dcf, selco, seltx],
        management_projections={"unlevered_free_cash_flow": ufcf},
        offered_consideration=SourcedValue(value=180.0, provenance=_prov(), unit="USD/share"),
    )


# ---------------------------------------------------------------------------
# Overlap arithmetic
# ---------------------------------------------------------------------------
def test_overlap_identical_is_one() -> None:
    assert _overlap_pct(100.0, 200.0, 100.0, 200.0) == 1.0


def test_overlap_disjoint_is_zero() -> None:
    assert _overlap_pct(100.0, 200.0, 300.0, 400.0) == 0.0
    assert _overlap_pct(100.0, 200.0, 0.0, 50.0) == 0.0


def test_overlap_partial_is_correct_fraction() -> None:
    # disclosed 100-200 (width 100); ours 150-250 -> intersection 150-200 = 50.
    assert _overlap_pct(100.0, 200.0, 150.0, 250.0) == pytest.approx(0.5)


def test_overlap_our_range_inside_disclosed() -> None:
    # ours entirely within disclosed: intersection = our width = 20; width = 100.
    assert _overlap_pct(0.0, 100.0, 40.0, 60.0) == pytest.approx(0.2)


def test_overlap_disclosed_inside_our_range_is_one() -> None:
    # disclosed entirely within ours: intersection = disclosed width -> 1.0.
    assert _overlap_pct(40.0, 60.0, 0.0, 100.0) == pytest.approx(1.0)


def test_overlap_none_when_input_missing() -> None:
    assert _overlap_pct(None, 200.0, 100.0, 200.0) is None
    assert _overlap_pct(100.0, 200.0, None, 200.0) is None


def test_overlap_none_when_disclosed_zero_width() -> None:
    assert _overlap_pct(150.0, 150.0, 100.0, 200.0) is None


# ---------------------------------------------------------------------------
# Hand-built disclosure — reproduction wiring + hand-computed ranges
# ---------------------------------------------------------------------------
def test_selected_companies_hand_computed() -> None:
    # Equity multiple 10x-20x on 100 $M metric, 10M shares, net cash -50 $M.
    #   low  = 100M * 10 / 10M = 100.00 ; high = 100M * 20 / 10M = 200.00
    # disclosed 150-250 (width 100) -> intersection 150-200 = 50 -> overlap 0.5.
    rep = run_fairness_differential(
        _hand_disclosure(),
        _empty_statements(),
        net_debt=-50.0 * _MILLIONS,
        shares=10_000_000.0,
    )
    selco = next(r for r in rep.reproductions if r.method == "Selected Companies")
    assert selco.our_low == pytest.approx(100.0)
    assert selco.our_high == pytest.approx(200.0)
    assert selco.overlap_pct == pytest.approx(0.5)
    # Equity multiple: net-debt bridge is NOT applied, so the net-cash figure
    # does not shift the per-share result.


def test_selected_transactions_hand_computed() -> None:
    # Same 10x-20x on 100 $M -> 100.00-200.00 ; disclosed 50-90 (width 40).
    # ours starts at 100 > 90 -> disjoint -> overlap 0.0.
    rep = run_fairness_differential(
        _hand_disclosure(),
        _empty_statements(),
        net_debt=0.0,
        shares=10_000_000.0,
    )
    seltx = next(r for r in rep.reproductions if r.method == "Selected Transactions")
    assert seltx.our_low == pytest.approx(100.0)
    assert seltx.our_high == pytest.approx(200.0)
    assert seltx.overlap_pct == 0.0


def test_dcf_reproduction_matches_direct_primitive() -> None:
    # The engine must pair LOW rate x HIGH multiple -> our_high and
    # HIGH rate x LOW multiple -> our_low, on explicit=[100M], terminal=200M.
    net_debt = -50.0 * _MILLIONS
    shares = 10_000_000.0
    explicit = [100.0 * _MILLIONS]
    terminal_metric = 200.0 * _MILLIONS
    expected_high = dcf_from_ufcf(
        explicit,
        0.10,
        TerminalAssumptions(method="exit_multiple", exit_ev_ebitda=25.0, mid_year_convention=True),
        net_debt=net_debt,
        shares=shares,
        terminal_metric=terminal_metric,
    ).implied_price_exit
    expected_low = dcf_from_ufcf(
        explicit,
        0.12,
        TerminalAssumptions(method="exit_multiple", exit_ev_ebitda=15.0, mid_year_convention=True),
        net_debt=net_debt,
        shares=shares,
        terminal_metric=terminal_metric,
    ).implied_price_exit

    rep = run_fairness_differential(
        _hand_disclosure(), _empty_statements(), net_debt=net_debt, shares=shares
    )
    dcf = next(r for r in rep.reproductions if r.method == "Discounted Cash Flow")
    assert dcf.our_low == pytest.approx(expected_low)
    assert dcf.our_high == pytest.approx(expected_high)
    assert dcf.our_low < dcf.our_high
    # disclosed 50-400 (width 350); overlap = hand-checked against the primitive.
    expected_overlap = _overlap_pct(50.0, 400.0, expected_low, expected_high)
    assert dcf.overlap_pct == pytest.approx(expected_overlap)


def test_report_shape_and_mean_overlap() -> None:
    rep = run_fairness_differential(
        _hand_disclosure(), _empty_statements(), net_debt=0.0, shares=10_000_000.0
    )
    assert len(rep.reproductions) == 3
    assert all(r.advisor == "Test Advisor" for r in rep.reproductions)
    assert all(r.deviation_note for r in rep.reproductions)
    mo = rep.mean_overlap
    assert mo is not None
    assert 0.0 <= mo <= 1.0


# ---------------------------------------------------------------------------
# Real deal — Qatalyst / ANSYS reproduction (measured, printed, not thresholded)
# ---------------------------------------------------------------------------
def test_flagship_fairness_reproduces_three_methodologies() -> None:
    rep = run_flagship_fairness()
    assert len(rep.reproductions) == 3

    print("\n=== Qatalyst / ANSYS fairness differential (OUR engine vs disclosed) ===")
    for r in rep.reproductions:
        assert r.disclosed_low is not None and r.disclosed_high is not None
        assert r.our_low is not None and r.our_high is not None
        assert r.overlap_pct is not None
        assert 0.0 <= r.overlap_pct <= 1.0
        print(
            f"{r.method:>22}: disclosed {r.disclosed_low:7.2f}-{r.disclosed_high:7.2f} | "
            f"ours {r.our_low:7.2f}-{r.our_high:7.2f} | overlap {r.overlap_pct * 100:5.1f}%"
        )
        print(f"    note: {r.deviation_note}")

    mo = rep.mean_overlap
    assert mo is not None
    assert 0.0 <= mo <= 1.0
    print(f"\nmean_overlap = {mo * 100:.1f}%")


def test_missing_assumptions_yield_honest_none() -> None:
    # A disclosure whose methodologies carry NO assumption ranges / projections:
    # the engine must return None ranges + None overlap, never fabricate a value.
    disc = FairnessDisclosure(
        advisor="Test Advisor",
        represents="TGT",
        methodologies=[
            AdvisorMethodology(method="Discounted Cash Flow", implied_range=_range(50.0, 400.0)),
            AdvisorMethodology(method="Selected Companies", implied_range=_range(150.0, 250.0)),
            AdvisorMethodology(method="Selected Transactions", implied_range=_range(50.0, 90.0)),
        ],
        management_projections={},
    )
    rep = run_fairness_differential(disc, _empty_statements(), net_debt=0.0, shares=10_000_000.0)
    assert len(rep.reproductions) == 3
    for r in rep.reproductions:
        assert r.our_low is None
        assert r.our_high is None
        assert r.overlap_pct is None
    assert rep.mean_overlap is None


def test_unrecognized_method_is_skipped() -> None:
    disc = FairnessDisclosure(
        advisor="Test Advisor",
        represents="TGT",
        methodologies=[
            AdvisorMethodology(method="Premiums Paid", implied_range=_range(50.0, 90.0)),
        ],
        management_projections={},
    )
    rep = run_fairness_differential(disc, _empty_statements(), net_debt=0.0, shares=10_000_000.0)
    assert rep.reproductions == []


def test_flagship_fairness_methods_present() -> None:
    rep = run_flagship_fairness()
    methods = {r.method for r in rep.reproductions}
    assert methods == {"Discounted Cash Flow", "Selected Companies", "Selected Transactions"}
