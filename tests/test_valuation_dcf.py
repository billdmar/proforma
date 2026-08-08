"""the valuation engine tests: WACC + FCFF DCF engine.

Ported from the thesis project's test_valuation_dcf.py, plus proforma-specific
coverage for the two fairness-differential additions: ``dcf(discount_rate=...)``
injection and the standalone ``dcf_from_ufcf`` stream discounter.

Self-contained: every fixture is a synthetic ``StatementSet`` + inputs built
here from the frozen contracts only (no dependency on other src engines). The
DCF golden case is hand-computed in the docstrings below and asserted to the
cent (abs tol 1e-6).
"""

from __future__ import annotations

from datetime import date

import pytest
from src.interfaces import StatementSet, TerminalAssumptions, WACCInputs
from src.schema import LineItem, Period, PeriodType
from src.valuation import DCFValuationEngine, dcf_from_ufcf


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------
def _period(end_year: int) -> Period:
    return Period(
        PeriodType.DURATION,
        end=date(end_year, 12, 31),
        start=date(end_year, 1, 1),
        fy=end_year,
        fp="FY",
    )


def _golden_statements() -> StatementSet:
    """1 historical + 3 projected columns.

    Projected drivers (indices 1..3):
        EBIT (OPERATING_INCOME): 100, 110, 120
        D&A  (DEP_AMORT):         20,  22,  24
        CAPEX (negative on CF):  -30, -33, -36   -> magnitudes 30, 33, 36
        CHANGE_IN_WC (cf sign):  -10, -11, -12   (WC build consumes cash)

    Last historical BS column (index 0), for the EV->equity bridge:
        SHORT_TERM_DEBT = 50, LONG_TERM_DEBT = 150,
        CASH = 100, SHORT_TERM_INVESTMENTS = 0  -> net_debt = 200 - 100 = 100
        SHARES_DILUTED = 10
    """
    periods = [_period(y) for y in (2024, 2025, 2026, 2027)]
    rows: dict[LineItem, list[float | None]] = {
        LineItem.OPERATING_INCOME: [None, 100.0, 110.0, 120.0],
        LineItem.DEP_AMORT: [None, 20.0, 22.0, 24.0],
        LineItem.CAPEX: [None, -30.0, -33.0, -36.0],
        LineItem.CHANGE_IN_WC: [None, -10.0, -11.0, -12.0],
        LineItem.SHORT_TERM_DEBT: [50.0, None, None, None],
        LineItem.LONG_TERM_DEBT: [150.0, None, None, None],
        LineItem.CASH: [100.0, None, None, None],
        LineItem.SHORT_TERM_INVESTMENTS: [0.0, None, None, None],
        LineItem.SHARES_DILUTED: [10.0, None, None, None],
    }
    return StatementSet(periods=periods, rows=rows, n_hist=1)


def _netcash_wacc() -> WACCInputs:
    """CAPM inputs giving Ke = 0.04 + 1.0*0.06 = 0.10; total_debt=0 -> WACC=0.10."""
    return WACCInputs(
        risk_free_rate=0.04,
        beta=1.0,
        equity_risk_premium=0.06,
        pretax_cost_of_debt=0.05,
        tax_rate=0.20,
        market_cap=1000.0,
        total_debt=0.0,
    )


# ---------------------------------------------------------------------------
# WACC
# ---------------------------------------------------------------------------
def test_wacc_weighted_golden():
    """Ke = 0.04 + 1.2*0.05 = 0.10; Kd_at = 0.06*(1-0.25) = 0.045.
    we=800/1000=0.8, wd=200/1000=0.2 -> WACC = 0.8*0.10 + 0.2*0.045 = 0.089.
    """
    eng = DCFValuationEngine()
    inputs = WACCInputs(
        risk_free_rate=0.04,
        beta=1.2,
        equity_risk_premium=0.05,
        pretax_cost_of_debt=0.06,
        tax_rate=0.25,
        market_cap=800.0,
        total_debt=200.0,
    )
    assert eng.wacc(inputs) == pytest.approx(0.089, abs=1e-12)


def test_wacc_net_cash_equals_cost_of_equity():
    """total_debt == 0 -> WACC collapses to Ke = rf + beta*ERP = 0.085."""
    eng = DCFValuationEngine()
    inputs = WACCInputs(
        risk_free_rate=0.03,
        beta=1.1,
        equity_risk_premium=0.05,
        pretax_cost_of_debt=0.06,  # must be ignored when total_debt == 0
        tax_rate=0.25,
        market_cap=500.0,
        total_debt=0.0,
    )
    cost_of_equity = 0.03 + 1.1 * 0.05
    assert eng.wacc(inputs) == pytest.approx(0.085, abs=1e-12)
    assert eng.wacc(inputs) == pytest.approx(cost_of_equity, abs=1e-12)


def test_wacc_zero_capital_raises():
    eng = DCFValuationEngine()
    inputs = WACCInputs(
        risk_free_rate=0.04,
        beta=1.0,
        equity_risk_premium=0.05,
        pretax_cost_of_debt=0.05,
        tax_rate=0.2,
        market_cap=0.0,
        total_debt=100.0,
    )
    # market_cap=0 with debt>0 keeps capital>0, so this is valid; force capital<=0.
    inputs.total_debt = -100.0
    with pytest.raises(ValueError, match="WACC weights undefined"):
        eng.wacc(inputs)


# ---------------------------------------------------------------------------
# DCF — hand-computed golden (end-year discounting, WACC=0.10, g=0.02)
# ---------------------------------------------------------------------------
def test_dcf_golden_both_terminal_methods():
    """FCFF = EBIT*(1-0.20) + D&A - |capex| + ΔWC_cf:
        Y1: 80 + 20 - 30 - 10 = 60
        Y2: 88 + 22 - 33 - 11 = 66
        Y3: 96 + 24 - 36 - 12 = 72
    DF (end-year, WACC=0.10): 1/1.1, 1/1.21, 1/1.331.
    PV explicit = 60/1.1 + 66/1.21 + 72/1.331 = 163.1855748...
    Gordon on NORMALIZED terminal FCFF (reinvestment-rate method):
        NOPAT_T = 120*0.8 = 96; RONIC = WACC + 0.03 = 0.13;
        reinvestment = g/RONIC = 0.02/0.13 = 0.153846; FCFF_T = 96*(1-0.153846)
        = 81.230769. TV = 81.230769*1.02/(0.10-0.02) = 1035.692308;
        PV = 1035.692308/1.331 = 778.1309599; EV_gordon = 941.3165347;
        equity = 841.3165347 -> price = 84.13165347
    Exit (a year-end sale, FULL-year discount = 1/1.331 here since mid_year=False):
        EBITDA_T = 120+24 = 144; TV = 144*8 = 1152; PV = 1152/1.331 = 865.5146506...
        EV_exit = 1028.7002254...  equity = 928.7002254 -> price = 92.87002254
    Bridge: net_debt = (50+150) - (100+0) = 100; shares = 10.
    """
    eng = DCFValuationEngine()
    stmts = _golden_statements()
    wacc_inputs = _netcash_wacc()
    terminal = TerminalAssumptions(
        method="both",
        terminal_growth=0.02,
        exit_ev_ebitda=8.0,
        mid_year_convention=False,
    )
    r = eng.dcf(stmts, wacc_inputs, terminal)

    assert r.wacc == pytest.approx(0.10, abs=1e-12)
    assert r.fcff_by_year == pytest.approx([60.0, 66.0, 72.0], abs=1e-9)
    assert r.discount_factors == pytest.approx([1 / 1.1, 1 / 1.21, 1 / 1.331], abs=1e-12)

    assert r.pv_explicit_fcff == pytest.approx(163.18557480, abs=1e-6)

    assert r.terminal_fcff_normalized == pytest.approx(81.23076923, abs=1e-6)
    assert r.terminal_value_gordon == pytest.approx(1035.69230769, abs=1e-6)
    assert r.pv_terminal_gordon == pytest.approx(778.13095995, abs=1e-6)
    assert r.enterprise_value_gordon == pytest.approx(941.31653470, abs=1e-6)

    assert r.terminal_value_exit == pytest.approx(1152.0, abs=1e-9)
    assert r.pv_terminal_exit == pytest.approx(865.51465064, abs=1e-6)
    assert r.enterprise_value_exit == pytest.approx(1028.70022539, abs=1e-6)

    assert r.net_debt == pytest.approx(100.0, abs=1e-9)
    assert r.minority_interest == 0.0
    assert r.shares_diluted == pytest.approx(10.0, abs=1e-12)

    assert r.equity_value_gordon == pytest.approx(841.31653470, abs=1e-6)
    assert r.equity_value_exit == pytest.approx(928.70022539, abs=1e-6)
    assert r.implied_price_gordon == pytest.approx(84.13165347, abs=1e-6)
    assert r.implied_price_exit == pytest.approx(92.87002254, abs=1e-6)


def test_dcf_terminal_growth_ge_wacc_raises():
    eng = DCFValuationEngine()
    stmts = _golden_statements()
    wacc_inputs = _netcash_wacc()  # WACC = 0.10
    # g == WACC
    with pytest.raises(ValueError, match="must be < WACC"):
        eng.dcf(stmts, wacc_inputs, TerminalAssumptions(terminal_growth=0.10))
    # g > WACC
    with pytest.raises(ValueError, match="must be < WACC"):
        eng.dcf(stmts, wacc_inputs, TerminalAssumptions(terminal_growth=0.15))


def test_dcf_mid_year_vs_end_year_discount_factors():
    """Mid-year year-t factor = 1/(1.1)^(t-0.5); end-year = 1/(1.1)^t.
    The mid-year factor exceeds the end-year factor by exactly sqrt(1.1) per year
    (cash arrives half a year sooner), so PV is strictly higher.
    """
    eng = DCFValuationEngine()
    stmts = _golden_statements()
    wacc_inputs = _netcash_wacc()

    mid = eng.dcf(
        stmts, wacc_inputs, TerminalAssumptions(terminal_growth=0.02, mid_year_convention=True)
    )
    end = eng.dcf(
        stmts, wacc_inputs, TerminalAssumptions(terminal_growth=0.02, mid_year_convention=False)
    )

    for t, (dfm, dfe) in enumerate(
        zip(mid.discount_factors, end.discount_factors, strict=True), start=1
    ):
        assert dfm == pytest.approx(1.0 / (1.1) ** (t - 0.5), abs=1e-12)
        assert dfe == pytest.approx(1.0 / (1.1) ** t, abs=1e-12)
        # Ratio between the two conventions is a constant sqrt(1+WACC).
        assert dfm / dfe == pytest.approx(1.1**0.5, abs=1e-12)

    assert mid.pv_explicit_fcff > end.pv_explicit_fcff
    assert mid.enterprise_value_gordon > end.enterprise_value_gordon


# ---------------------------------------------------------------------------
# DCF — proforma addition: injected discount_rate (fairness differential)
# ---------------------------------------------------------------------------
def test_dcf_discount_rate_injection_uses_supplied_rate():
    """dcf(discount_rate=0.11) uses 0.11 exactly, skipping the CAPM build, while
    still reading wacc_inputs.tax_rate (0.20) for the unlevered NOPAT term.

    FCFF unchanged: [60, 66, 72]. End-year DFs at r=0.11:
        1/1.11, 1/1.11^2, 1/1.11^3  (1.11^2=1.2321, 1.11^3=1.367631)
    Expected pv_explicit is recomputed inline (independent arithmetic).
    """
    eng = DCFValuationEngine()
    stmts = _golden_statements()
    # market_cap/total_debt would give a CAPM WACC of 0.089 — but debt=0 here
    # gives 0.10; either way the injected 0.11 must win and differ.
    wacc_inputs = _netcash_wacc()  # CAPM WACC = 0.10, tax_rate = 0.20
    terminal = TerminalAssumptions(
        method="both", terminal_growth=0.02, exit_ev_ebitda=8.0, mid_year_convention=False
    )

    r = eng.dcf(stmts, wacc_inputs, terminal, discount_rate=0.11)
    assert r.wacc == 0.11  # supplied rate used verbatim

    # Independent hand arithmetic for the explicit PV at r=0.11.
    fcff = [60.0, 66.0, 72.0]
    expected_pv = sum(f / (1.11**t) for t, f in enumerate(fcff, start=1))
    assert r.pv_explicit_fcff == pytest.approx(expected_pv, abs=1e-9)
    assert r.fcff_by_year == pytest.approx(fcff, abs=1e-9)

    # The injected-rate path must differ from the CAPM (0.10) path.
    capm = eng.dcf(stmts, wacc_inputs, terminal)  # discount_rate=None -> WACC=0.10
    assert capm.wacc == pytest.approx(0.10, abs=1e-12)
    assert r.implied_price_gordon != pytest.approx(capm.implied_price_gordon, abs=1e-6)
    assert r.implied_price_exit != pytest.approx(capm.implied_price_exit, abs=1e-6)


# ---------------------------------------------------------------------------
# dcf_from_ufcf — proforma addition: discount a SUPPLIED UFCF stream directly
# ---------------------------------------------------------------------------
def test_dcf_from_ufcf_exit_multiple_hand_computed():
    """Supplied UFCF stream [100, 110, 120] at r=0.10, end-year discounting.

    DFs: 1/1.1, 1/1.21, 1/1.331.
    PV explicit = 100/1.1 + 110/1.21 + 120/1.331  (recomputed inline).
    Exit-multiple terminal: terminal_metric = 120 (terminal-year UFCF), multiple
        (exit_ev_ebitda) = 15  -> TV = 120*15 = 1800; discounted FULL-year at
        1/1.1^3 = 1/1.331.
    Bridge: net_debt = 200, shares = 50.
    """
    ufcf = [100.0, 110.0, 120.0]
    r = 0.10
    terminal = TerminalAssumptions(
        method="exit_multiple", exit_ev_ebitda=15.0, mid_year_convention=False
    )
    res = dcf_from_ufcf(ufcf, r, terminal, net_debt=200.0, shares=50.0, terminal_metric=120.0)

    assert res.wacc == 0.10
    assert res.fcff_by_year == pytest.approx(ufcf, abs=1e-12)
    assert res.discount_factors == pytest.approx([1 / 1.1, 1 / 1.21, 1 / 1.331], abs=1e-12)

    pv_explicit = sum(f / (1.1**t) for t, f in enumerate(ufcf, start=1))
    assert res.pv_explicit_fcff == pytest.approx(pv_explicit, abs=1e-9)

    tv_exit = 120.0 * 15.0
    pv_terminal_exit = tv_exit / (1.1**3)
    ev_exit = pv_explicit + pv_terminal_exit
    equity_exit = ev_exit - 200.0
    price_exit = equity_exit / 50.0

    assert res.terminal_value_exit == pytest.approx(tv_exit, abs=1e-9)
    assert res.pv_terminal_exit == pytest.approx(pv_terminal_exit, abs=1e-9)
    assert res.enterprise_value_exit == pytest.approx(ev_exit, abs=1e-6)
    assert res.equity_value_exit == pytest.approx(equity_exit, abs=1e-6)
    assert res.implied_price_exit == pytest.approx(price_exit, abs=1e-6)

    # method="exit_multiple" -> Gordon fields untouched (0.0).
    assert res.terminal_value_gordon == 0.0
    assert res.pv_terminal_gordon == 0.0


def test_dcf_from_ufcf_gordon_optional():
    """method='both' populates the Gordon perpetuity on the LAST supplied UFCF
    (no RONIC normalization — the disclosed stream is not re-normalized).

    ufcf[-1]=120, g=0.03, r=0.10 -> TV = 120*1.03/(0.10-0.03) = 1765.714286,
    discounted at the final explicit-year factor (end-year 1/1.331).
    """
    ufcf = [100.0, 110.0, 120.0]
    terminal = TerminalAssumptions(
        method="both", terminal_growth=0.03, exit_ev_ebitda=15.0, mid_year_convention=False
    )
    res = dcf_from_ufcf(ufcf, 0.10, terminal, net_debt=0.0, shares=50.0, terminal_metric=120.0)
    tv_gordon = 120.0 * 1.03 / (0.10 - 0.03)
    assert res.terminal_value_gordon == pytest.approx(tv_gordon, abs=1e-6)
    assert res.pv_terminal_gordon == pytest.approx(tv_gordon / (1.1**3), abs=1e-6)
    # Exit still populated too.
    assert res.terminal_value_exit == pytest.approx(120.0 * 15.0, abs=1e-9)


def test_dcf_from_ufcf_no_terminal_metric_zero_exit():
    """Without a terminal_metric the exit-multiple terminal is 0.0; only the
    explicit PV (and optional Gordon) contribute."""
    ufcf = [100.0, 110.0]
    terminal = TerminalAssumptions(method="exit_multiple", mid_year_convention=False)
    res = dcf_from_ufcf(ufcf, 0.10, terminal, net_debt=0.0, shares=10.0)
    assert res.terminal_value_exit == 0.0
    assert res.pv_terminal_exit == 0.0
    assert res.enterprise_value_exit == pytest.approx(res.pv_explicit_fcff, abs=1e-12)


def test_dcf_from_ufcf_validates_inputs():
    terminal = TerminalAssumptions(method="exit_multiple")
    with pytest.raises(ValueError, match="non-empty ufcf"):
        dcf_from_ufcf([], 0.10, terminal, net_debt=0.0, shares=10.0)
    with pytest.raises(ValueError, match="positive share count"):
        dcf_from_ufcf([100.0], 0.10, terminal, net_debt=0.0, shares=0.0)


# ---------------------------------------------------------------------------
# DCF — edge cases / honest-unknown guards
# ---------------------------------------------------------------------------
def test_dcf_missing_ebit_raises():
    eng = DCFValuationEngine()
    stmts = _golden_statements()
    stmts.rows[LineItem.OPERATING_INCOME] = [None, 100.0, None, 120.0]  # gap in projection
    with pytest.raises(ValueError, match="OPERATING_INCOME"):
        eng.dcf(
            stmts, _netcash_wacc(), TerminalAssumptions(terminal_growth=0.02, exit_ev_ebitda=8.0)
        )


def test_dcf_no_projected_periods_raises():
    eng = DCFValuationEngine()
    periods = [_period(2024)]
    rows: dict[LineItem, list[float | None]] = {LineItem.OPERATING_INCOME: [100.0]}
    stmts = StatementSet(periods=periods, rows=rows, n_hist=1)
    with pytest.raises(ValueError, match="no projected periods"):
        eng.dcf(stmts, _netcash_wacc(), TerminalAssumptions(terminal_growth=0.02))


def test_dcf_da_falls_back_to_cf_tag():
    """When DEP_AMORT is absent, the D&A add-back falls back to DA_CF."""
    eng = DCFValuationEngine()
    stmts = _golden_statements()
    del stmts.rows[LineItem.DEP_AMORT]
    stmts.rows[LineItem.DA_CF] = [None, 20.0, 22.0, 24.0]
    r = eng.dcf(
        stmts,
        _netcash_wacc(),
        TerminalAssumptions(terminal_growth=0.02, exit_ev_ebitda=8.0, mid_year_convention=False),
    )
    # Identical to the golden case (same D&A magnitudes, now via DA_CF).
    assert r.fcff_by_year == pytest.approx([60.0, 66.0, 72.0], abs=1e-9)
    assert r.enterprise_value_exit == pytest.approx(1028.70022544, abs=1e-6)


def test_dcf_missing_da_and_capex_default_to_zero():
    """Absent D&A / capex are modeling-default 0.0 (not fabricated)."""
    eng = DCFValuationEngine()
    periods = [_period(y) for y in (2024, 2025)]
    rows: dict[LineItem, list[float | None]] = {
        LineItem.OPERATING_INCOME: [None, 100.0],
        LineItem.SHARES_DILUTED: [10.0, None],
        # no D&A, no capex, no ΔWC, no debt/cash
    }
    stmts = StatementSet(periods=periods, rows=rows, n_hist=1)
    r = eng.dcf(
        stmts,
        _netcash_wacc(),
        TerminalAssumptions(terminal_growth=0.02, exit_ev_ebitda=8.0, mid_year_convention=False),
    )
    # FCFF = 100*(1-0.2) = 80; net_debt = 0.
    assert r.fcff_by_year == pytest.approx([80.0], abs=1e-9)
    assert r.net_debt == pytest.approx(0.0, abs=1e-12)


def test_dcf_missing_shares_raises():
    eng = DCFValuationEngine()
    stmts = _golden_statements()
    del stmts.rows[LineItem.SHARES_DILUTED]
    with pytest.raises(ValueError, match="diluted share count"):
        eng.dcf(
            stmts, _netcash_wacc(), TerminalAssumptions(terminal_growth=0.02, exit_ev_ebitda=8.0)
        )


def test_dcf_shares_fall_back_to_outstanding():
    eng = DCFValuationEngine()
    stmts = _golden_statements()
    del stmts.rows[LineItem.SHARES_DILUTED]
    stmts.rows[LineItem.SHARES_OUTSTANDING] = [10.0, None, None, None]
    r = eng.dcf(
        stmts,
        _netcash_wacc(),
        TerminalAssumptions(terminal_growth=0.02, exit_ev_ebitda=8.0, mid_year_convention=False),
    )
    assert r.shares_diluted == pytest.approx(10.0, abs=1e-12)
    assert r.implied_price_gordon == pytest.approx(84.13165347, abs=1e-6)
