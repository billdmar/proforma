"""Golden, hand-computed tests for the combination engine.

Every asserted number is derived by hand in the docstrings so the merger-model
mechanics are pinned, not merely reproduced. The engine takes two standalone
``StatementSet``s; SA-models builds the real ones in parallel, so here we hand-
build small synthetic statement sets (we own the test inputs) and do not import
any sibling engine module.

Tax convention under test (the incremental A/D build — see engine docstring):
    pro forma NI = acq_ni + tgt_ni
                   − new_debt·rate·(1−t) − cash_used·yield·(1−t)
                   − stepup_D&A·(1−t) + synergies·(1−t)
"""

from __future__ import annotations

from datetime import date

import pytest
from src.combine import CombinationEngine
from src.interfaces import (
    Consideration,
    DealAssumptions,
    DealResult,
    PurchasePriceAllocation,
    SourcesAndUses,
    StatementSet,
    SynergyCase,
)
from src.schema import LineItem, Period, PeriodType

# --------------------------------------------------------------------------- #
# fixtures / builders (we own all test inputs)
# --------------------------------------------------------------------------- #
YEARS = [
    Period(PeriodType.DURATION, end=date(y, 12, 31), start=date(y, 1, 1), fp="FY")
    for y in (2025, 2026, 2027)
]
BS_YEARS = [Period(PeriodType.INSTANT, end=date(y, 12, 31)) for y in (2025, 2026, 2027)]


def _income_statements(
    net_income: float, shares: float, revenue: float = 0.0, n: int = 3
) -> StatementSet:
    """A projection-only StatementSet carrying just the IS lines A/D needs.

    Flat across ``n`` years; PRETAX/TAX left absent so income-line reconciliation
    is exercised only in the balance/bridge tests that set them explicitly.
    """
    return StatementSet(
        periods=YEARS[:n],
        rows={
            LineItem.REVENUE: [revenue] * n,
            LineItem.NET_INCOME: [net_income] * n,
            LineItem.SHARES_DILUTED: [shares] * n,
        },
        n_hist=0,
    )


def _no_synergy(n: int = 3) -> SynergyCase:
    return SynergyCase(name="none", run_rate_annual=0.0, phase_in=[0.0] * n)


def _clean_deal(new_shares: float = 0.0, **overrides) -> DealResult:
    """A DealResult with zeroed PPA/S&U unless overridden — the combination
    engine only reads consideration.new_shares_issued, .aggregate_stock_value,
    ppa.*, and incremental_da_annual."""
    consideration = Consideration(
        cash_per_share=overrides.pop("cash_per_share", 0.0),
        stock_per_share_value=0.0,
        total_per_share=0.0,
        target_shares=0.0,
        aggregate_cash=0.0,
        aggregate_stock_value=overrides.pop("aggregate_stock_value", 0.0),
        equity_purchase_price=0.0,
        new_shares_issued=new_shares,
    )
    ppa = overrides.pop(
        "ppa",
        PurchasePriceAllocation(
            equity_purchase_price=0.0,
            target_book_equity=0.0,
            target_existing_goodwill=0.0,
            identifiable_net_assets_at_book=0.0,
            intangible_step_up=0.0,
            ppe_step_up=0.0,
            deferred_tax_liability=0.0,
            net_identifiable_assets=0.0,
            goodwill=0.0,
        ),
    )
    return DealResult(
        consideration=consideration,
        sources_and_uses=SourcesAndUses(sources={}, uses={}),
        ppa=ppa,
        incremental_da_annual=overrides.pop("incremental_da_annual", 0.0),
    )


ENGINE = CombinationEngine()


# --------------------------------------------------------------------------- #
# all-stock accretion/dilution — classic P/E rule
# --------------------------------------------------------------------------- #
def test_all_stock_higher_pe_buys_lower_pe_is_accretive():
    """Acquirer P/E 20 (NI 1000, 100 shares, price 200) buys target P/E 12.5
    (NI 400) all-stock at no premium. Target equity value = 400 × 12.5 = 5000;
    new shares = 5000 / 200 = 25. Pro forma NI 1400 / 125 shares = 11.20 EPS
    vs standalone 10.00 → +12.0% accretion (higher-P/E buyer ⇒ accretive)."""
    acquirer = _income_statements(net_income=1000.0, shares=100.0)
    target = _income_statements(net_income=400.0, shares=40.0)
    deal = _clean_deal(new_shares=25.0)

    result = ENGINE.combine(acquirer, target, deal, DealAssumptions(), _no_synergy())
    b = result.eps_bridge[0]

    assert b.pro_forma_shares == 125.0
    assert b.acquirer_standalone_eps == pytest.approx(10.0)
    assert b.pro_forma_eps == pytest.approx(11.20)
    assert b.accretion_dilution_pct == pytest.approx(0.12)
    assert b.accretion_dilution_pct > 0  # sign: accretive


def test_all_stock_lower_pe_buys_higher_pe_is_dilutive():
    """Reverse: acquirer P/E 12.5 buying target P/E 20 all-stock is dilutive —
    same machinery, opposite sign."""
    acquirer = _income_statements(net_income=400.0, shares=40.0)  # price implied 125
    target = _income_statements(net_income=1000.0, shares=100.0)
    # target equity value at P/E 20 = 20000; acquirer price = 400*12.5/40 = 125;
    # new shares = 20000/125 = 160. PF NI 1400 / 200 = 7.00 vs standalone 10.00.
    deal = _clean_deal(new_shares=160.0)

    b = ENGINE.combine(acquirer, target, deal, DealAssumptions(), _no_synergy()).eps_bridge[0]
    assert b.acquirer_standalone_eps == pytest.approx(10.0)
    assert b.pro_forma_eps == pytest.approx(7.0)
    assert b.accretion_dilution_pct == pytest.approx(-0.30)
    assert b.accretion_dilution_pct < 0  # sign: dilutive


# --------------------------------------------------------------------------- #
# all-cash accretion/dilution — earnings yield vs after-tax cost of funds
# --------------------------------------------------------------------------- #
def test_all_cash_debt_funded_accretion():
    """All-cash, all-debt-funded, no new shares. Acquirer NI 1000 / 100 shares
    (EPS 10). Target NI 400. New debt 5000 @ 5% = 250 interest; after-tax at
    t=20% = 200. PF NI = 1000 + 400 − 200 = 1200 / 100 = 12.00 vs 10.00 →
    +20.0% accretion (target earnings yield 400/5000=8% beats the 4% after-tax
    cost of the debt)."""
    acquirer = _income_statements(net_income=1000.0, shares=100.0)
    target = _income_statements(net_income=400.0, shares=40.0)
    deal = _clean_deal(new_shares=0.0)
    da = DealAssumptions(new_debt=5000.0, new_debt_rate=0.05, marginal_tax_rate=0.20)

    b = ENGINE.combine(acquirer, target, deal, da, _no_synergy()).eps_bridge[0]
    assert b.incremental_interest_aftertax == pytest.approx(200.0)  # 250 pre-tax × (1 − 0.20)
    assert b.pro_forma_net_income == pytest.approx(1200.0)
    assert b.pro_forma_eps == pytest.approx(12.0)
    assert b.accretion_dilution_pct == pytest.approx(0.20)


def test_all_cash_expensive_debt_is_dilutive():
    """Same deal but debt @ 20% (after-tax cost 16% > 8% earnings yield). Interest
    5000×0.20=1000, after-tax 800. PF NI = 1400 − 800 = 600 / 100 = 6.00 →
    −40% dilution. Confirms the earnings-yield-vs-cost-of-funds sign."""
    acquirer = _income_statements(net_income=1000.0, shares=100.0)
    target = _income_statements(net_income=400.0, shares=40.0)
    deal = _clean_deal(new_shares=0.0)
    da = DealAssumptions(new_debt=5000.0, new_debt_rate=0.20, marginal_tax_rate=0.20)

    b = ENGINE.combine(acquirer, target, deal, da, _no_synergy()).eps_bridge[0]
    assert b.pro_forma_eps == pytest.approx(6.0)
    assert b.accretion_dilution_pct == pytest.approx(-0.40)


def test_foregone_cash_yield_reduces_income():
    """Cash-on-hand leg: 2000 cash used at 3% foregone yield = 60 pre-tax, 48
    after-tax at t=20%. PF NI = 1400 − 48 = 1352."""
    acquirer = _income_statements(net_income=1000.0, shares=100.0)
    target = _income_statements(net_income=400.0, shares=40.0)
    deal = _clean_deal(new_shares=0.0)
    da = DealAssumptions(cash_on_hand_used=2000.0, foregone_cash_yield=0.03, marginal_tax_rate=0.20)

    b = ENGINE.combine(acquirer, target, deal, da, _no_synergy()).eps_bridge[0]
    assert b.foregone_interest_aftertax == pytest.approx(48.0)  # 60 pre-tax × (1 − 0.20)
    assert b.pro_forma_net_income == pytest.approx(1352.0)


# --------------------------------------------------------------------------- #
# synergy phase-in
# --------------------------------------------------------------------------- #
def test_synergy_phase_in_ramps_and_more_synergies_more_accretive():
    """Run-rate 500 pre-tax, phase-in [0.25, 0.5, 1.0], t=20% ⇒ after-tax added
    NI of 100, 200, 400 across the three years. All-stock, no premium base
    (acquirer NI 1000/100 sh, target NI 400, 25 new shares → base PF NI 1400).
    Year EPS = (1400 + synergy_at)/125."""
    acquirer = _income_statements(net_income=1000.0, shares=100.0)
    target = _income_statements(net_income=400.0, shares=40.0)
    deal = _clean_deal(new_shares=25.0)
    da = DealAssumptions(marginal_tax_rate=0.20)
    syn = SynergyCase(
        name="mgmt", run_rate_annual=500.0, phase_in=[0.25, 0.5, 1.0], is_disclosed=True
    )

    bridge = ENGINE.combine(acquirer, target, deal, da, syn).eps_bridge
    assert [b.synergies_aftertax for b in bridge] == pytest.approx([100.0, 200.0, 400.0])
    assert [b.pro_forma_net_income for b in bridge] == pytest.approx([1500.0, 1600.0, 1800.0])
    # accretion strictly increases as synergies ramp in.
    ad = [b.accretion_dilution_pct for b in bridge]
    assert ad[0] < ad[1] < ad[2]

    # more synergies ⇒ more accretive at a fixed year.
    syn_big = SynergyCase(name="big", run_rate_annual=1000.0, phase_in=[0.25, 0.5, 1.0])
    bridge_big = ENGINE.combine(acquirer, target, deal, da, syn_big).eps_bridge
    for small, big in zip(bridge, bridge_big, strict=True):
        assert big.accretion_dilution_pct > small.accretion_dilution_pct


def test_incremental_da_is_dilutive():
    """Step-up D&A of 250/yr pre-tax, t=20% ⇒ 200 after-tax drag. All-stock base
    PF NI 1400 → 1200; EPS 1200/125 = 9.60 vs standalone 10.00 → −4.0%."""
    acquirer = _income_statements(net_income=1000.0, shares=100.0)
    target = _income_statements(net_income=400.0, shares=40.0)
    deal = _clean_deal(new_shares=25.0, incremental_da_annual=250.0)
    da = DealAssumptions(marginal_tax_rate=0.20)

    b = ENGINE.combine(acquirer, target, deal, da, _no_synergy()).eps_bridge[0]
    assert b.incremental_da_aftertax == pytest.approx(200.0)
    assert b.pro_forma_eps == pytest.approx(9.60)
    assert b.accretion_dilution_pct == pytest.approx(-0.04)


# --------------------------------------------------------------------------- #
# EPS bridge recompute — independently reassemble PF EPS from bridge components
# --------------------------------------------------------------------------- #
def test_eps_bridge_recompute_to_the_cent():
    """Recompute pro forma EPS from the bridge's own fields and assert it equals
    the reported pro_forma_eps. Uses a fully-loaded deal (all four adjustments +
    synergies + new shares) so every field participates."""
    acquirer = _income_statements(net_income=1000.0, shares=100.0)
    target = _income_statements(net_income=400.0, shares=40.0)
    deal = _clean_deal(new_shares=25.0, incremental_da_annual=150.0)
    da = DealAssumptions(
        new_debt=5000.0,
        new_debt_rate=0.05,
        cash_on_hand_used=1000.0,
        foregone_cash_yield=0.02,
        marginal_tax_rate=0.20,
    )
    syn = SynergyCase(name="s", run_rate_annual=300.0, phase_in=[0.5, 1.0, 1.0])

    for b in ENGINE.combine(acquirer, target, deal, da, syn).eps_bridge:
        # All legs are stored after-tax → a pure additive walk.
        recomputed_ni = (
            b.acquirer_standalone_ni
            + b.target_standalone_ni
            - b.incremental_interest_aftertax
            - b.foregone_interest_aftertax
            - b.incremental_da_aftertax
            + b.synergies_aftertax
        )
        assert recomputed_ni == pytest.approx(b.pro_forma_net_income)
        assert recomputed_ni / b.pro_forma_shares == pytest.approx(b.pro_forma_eps)


# --------------------------------------------------------------------------- #
# pro forma balance sheet balances every projected period
# --------------------------------------------------------------------------- #
def _balanced_bs_statements(
    *,
    net_income: float,
    shares: float,
    ta: float,
    tl: float,
    te: float,
    cash: float,
    goodwill: float,
    common_stock: float,
    retained: float,
    n: int = 3,
) -> StatementSet:
    """A StatementSet with an already-balancing balance sheet (TA = TL + TE) plus
    the IS lines the engine reads."""
    return StatementSet(
        periods=YEARS[:n] + BS_YEARS[:n],
        rows={
            LineItem.NET_INCOME: [net_income] * (2 * n),
            LineItem.SHARES_DILUTED: [shares] * (2 * n),
            LineItem.CASH: [cash] * (2 * n),
            LineItem.GOODWILL: [goodwill] * (2 * n),
            LineItem.INTANGIBLES: [0.0] * (2 * n),
            LineItem.PPE_NET: [0.0] * (2 * n),
            LineItem.LONG_TERM_DEBT: [0.0] * (2 * n),
            LineItem.DEFERRED_TAX_LIABILITIES: [0.0] * (2 * n),
            LineItem.COMMON_STOCK: [common_stock] * (2 * n),
            LineItem.RETAINED_EARNINGS: [retained] * (2 * n),
            LineItem.TREASURY_STOCK: [0.0] * (2 * n),
            LineItem.AOCI: [0.0] * (2 * n),
            LineItem.TOTAL_ASSETS: [ta] * (2 * n),
            LineItem.TOTAL_LIABILITIES: [tl] * (2 * n),
            LineItem.TOTAL_EQUITY: [te] * (2 * n),
        },
        n_hist=0,
    )


def test_pro_forma_balance_sheet_balances_every_period():
    """Acquirer TA 5000 = TL 2000 + TE 3000; target TA 1800 = TL 800 + TE 1000.
    Deal: 500 cash used, 1000 new debt, target GW 200 written off and 1400 new
    goodwill, 300 intangible + 100 PP&E step-up, 100 DTL, 1000 stock issued, no
    fees. Every projected period's pro forma A must equal L + E within $1."""
    acquirer = _balanced_bs_statements(
        net_income=1000.0,
        shares=100.0,
        ta=5000.0,
        tl=2000.0,
        te=3000.0,
        cash=1500.0,
        goodwill=0.0,
        common_stock=1000.0,
        retained=2000.0,
    )
    target = _balanced_bs_statements(
        net_income=400.0,
        shares=40.0,
        ta=1800.0,
        tl=800.0,
        te=1000.0,
        cash=600.0,
        goodwill=200.0,
        common_stock=400.0,
        retained=600.0,
    )
    ppa = PurchasePriceAllocation(
        equity_purchase_price=2400.0,
        target_book_equity=1000.0,
        target_existing_goodwill=200.0,
        identifiable_net_assets_at_book=800.0,
        intangible_step_up=300.0,
        ppe_step_up=100.0,
        deferred_tax_liability=100.0,
        net_identifiable_assets=1100.0,
        goodwill=1400.0,
    )
    deal = _clean_deal(new_shares=5.0, aggregate_stock_value=1000.0, ppa=ppa)
    da = DealAssumptions(
        new_debt=1000.0,
        cash_on_hand_used=500.0,
        target_existing_goodwill_written_off=True,
        marginal_tax_rate=0.20,
    )

    pf = ENGINE.combine(acquirer, target, deal, da, _no_synergy()).proforma_statements
    for j in range(len(pf.periods)):
        ta = pf.series(LineItem.TOTAL_ASSETS)[j]
        tl = pf.series(LineItem.TOTAL_LIABILITIES)[j]
        te = pf.series(LineItem.TOTAL_EQUITY)[j]
        assert abs(ta - (tl + te)) < 1.0
    # sanity: new goodwill landed (0 + 200 combined − 200 written off + 1400).
    assert pf.series(LineItem.GOODWILL)[0] == pytest.approx(1400.0)
    # cash drawn down by the 500 used.
    assert pf.series(LineItem.CASH)[0] == pytest.approx(1600.0)


def test_income_statement_lines_reconcile_to_net_income():
    """When PRETAX/TAX are present, PF pretax − PF tax must equal PF net income.
    Acquirer pretax 1250, tax 250 (NI 1000); target pretax 500, tax 100 (NI 400).
    Deal: 250 stepup D&A, 200 synergies, t=20%. Combined adj pretax = −50 →
    PF pretax 1700, PF tax = 350 + (−50·0.2)=340 → NI 1360."""
    n = 3
    acquirer = StatementSet(
        periods=YEARS[:n],
        rows={
            LineItem.NET_INCOME: [1000.0] * n,
            LineItem.PRETAX_INCOME: [1250.0] * n,
            LineItem.INCOME_TAX_EXPENSE: [250.0] * n,
            LineItem.OPERATING_INCOME: [1300.0] * n,
            LineItem.SHARES_DILUTED: [100.0] * n,
        },
        n_hist=0,
    )
    target = StatementSet(
        periods=YEARS[:n],
        rows={
            LineItem.NET_INCOME: [400.0] * n,
            LineItem.PRETAX_INCOME: [500.0] * n,
            LineItem.INCOME_TAX_EXPENSE: [100.0] * n,
            LineItem.OPERATING_INCOME: [520.0] * n,
            LineItem.SHARES_DILUTED: [40.0] * n,
        },
        n_hist=0,
    )
    deal = _clean_deal(new_shares=25.0, incremental_da_annual=250.0)
    da = DealAssumptions(marginal_tax_rate=0.20)
    syn = SynergyCase(name="s", run_rate_annual=200.0, phase_in=[1.0, 1.0, 1.0])

    pf = ENGINE.combine(acquirer, target, deal, da, syn).proforma_statements
    for j in range(len(pf.periods)):
        pretax = pf.series(LineItem.PRETAX_INCOME)[j]
        tax = pf.series(LineItem.INCOME_TAX_EXPENSE)[j]
        ni = pf.series(LineItem.NET_INCOME)[j]
        assert pretax == pytest.approx(1700.0)
        assert tax == pytest.approx(340.0)
        assert pretax - tax == pytest.approx(ni)
        assert ni == pytest.approx(1360.0)
    # operating income absorbs step-up D&A drag and synergies: 1820 − 250 + 200.
    assert pf.series(LineItem.OPERATING_INCOME)[0] == pytest.approx(1770.0)


# --------------------------------------------------------------------------- #
# contribution analysis — ownership sums to 1.0
# --------------------------------------------------------------------------- #
def test_contribution_ownership_sums_to_one():
    """Acquirer 100 existing shares, 25 issued to target ⇒ 80% / 20% ownership
    of the 125-share combined entity, summing to 1.0. Revenue/EBITDA/NI reflect
    each standalone (first projected year)."""
    acquirer = _income_statements(net_income=1000.0, shares=100.0, revenue=8000.0)
    target = _income_statements(net_income=400.0, shares=40.0, revenue=2000.0)
    # add EBITDA components.
    acquirer.rows[LineItem.OPERATING_INCOME] = [1300.0] * 3
    acquirer.rows[LineItem.DEP_AMORT] = [200.0] * 3
    target.rows[LineItem.OPERATING_INCOME] = [500.0] * 3
    target.rows[LineItem.DEP_AMORT] = [100.0] * 3
    deal = _clean_deal(new_shares=25.0)

    c = ENGINE.combine(acquirer, target, deal, DealAssumptions(), _no_synergy()).contribution
    assert c.acquirer_ownership_pct == pytest.approx(0.80)
    assert c.target_ownership_pct == pytest.approx(0.20)
    assert c.acquirer_ownership_pct + c.target_ownership_pct == pytest.approx(1.0)
    assert c.acquirer_revenue == 8000.0 and c.target_revenue == 2000.0
    assert c.acquirer_ebitda == pytest.approx(1500.0)  # 1300 + 200
    assert c.target_ebitda == pytest.approx(600.0)  # 500 + 100
    assert c.acquirer_net_income == 1000.0 and c.target_net_income == 400.0


def test_zero_shares_and_missing_lines_are_safe():
    """Degenerate guards: zero share counts → EPS 0.0 (not a divide error) and
    ownership 0.0; a line absent from BOTH sides stays None in the pro forma."""
    empty = StatementSet(periods=YEARS[:1], rows={}, n_hist=0)
    deal = _clean_deal(new_shares=0.0)
    result = ENGINE.combine(empty, empty, deal, DealAssumptions(), _no_synergy(n=1))
    b = result.eps_bridge[0]
    assert b.acquirer_standalone_eps == 0.0
    assert b.pro_forma_eps == 0.0
    assert b.accretion_dilution_pct is None
    assert result.contribution.acquirer_ownership_pct == 0.0
    # goodwill absent on both inputs → honest unknown, not 0.
    assert result.proforma_statements.series(LineItem.GOODWILL) == [None]


def test_pretax_present_but_tax_absent_leaves_tax_untouched():
    """If PRETAX is disclosed but the TAX line is absent on both sides, the pro
    forma pretax is still adjusted while the tax line is left absent (honest
    unknown) rather than fabricated."""
    n = 1
    acquirer = StatementSet(
        periods=YEARS[:n],
        rows={
            LineItem.NET_INCOME: [1000.0] * n,
            LineItem.PRETAX_INCOME: [1250.0] * n,
            LineItem.SHARES_DILUTED: [100.0] * n,
        },
        n_hist=0,
    )
    target = StatementSet(
        periods=YEARS[:n],
        rows={
            LineItem.NET_INCOME: [400.0] * n,
            LineItem.PRETAX_INCOME: [500.0] * n,
            LineItem.SHARES_DILUTED: [40.0] * n,
        },
        n_hist=0,
    )
    deal = _clean_deal(new_shares=25.0, incremental_da_annual=250.0)
    da = DealAssumptions(marginal_tax_rate=0.20)

    pf = ENGINE.combine(acquirer, target, deal, da, _no_synergy(n=1)).proforma_statements
    # adj pretax = -250 D&A → 1750 - 250 = 1500.
    assert pf.series(LineItem.PRETAX_INCOME)[0] == pytest.approx(1500.0)
    assert pf.series(LineItem.INCOME_TAX_EXPENSE) == [None]


def test_row_shorter_than_horizon_reads_as_missing():
    """A row list shorter than the period count is an honest unknown past its
    end (out-of-bounds guard), not an index error: acquirer NET_INCOME covers
    only year 1, so year-2 acquirer NI reads as 0/absent."""
    acquirer = StatementSet(
        periods=YEARS[:2],
        rows={
            LineItem.NET_INCOME: [1000.0],  # only one entry for a 2-year horizon
            LineItem.SHARES_DILUTED: [100.0, 100.0],
        },
        n_hist=0,
    )
    target = _income_statements(net_income=400.0, shares=40.0, n=2)
    deal = _clean_deal(new_shares=0.0)
    bridge = ENGINE.combine(acquirer, target, deal, DealAssumptions(), _no_synergy(n=2)).eps_bridge
    assert bridge[0].acquirer_standalone_ni == 1000.0
    assert bridge[1].acquirer_standalone_ni == 0.0  # missing → 0, no IndexError


def test_horizon_truncates_to_shorter_side():
    """If the target projects fewer years than the acquirer, the combination
    horizon is the shorter of the two (no fabricated target periods)."""
    acquirer = _income_statements(net_income=1000.0, shares=100.0, n=3)
    target = _income_statements(net_income=400.0, shares=40.0, n=2)
    deal = _clean_deal(new_shares=25.0)
    result = ENGINE.combine(acquirer, target, deal, DealAssumptions(), _no_synergy(n=3))
    assert len(result.eps_bridge) == 2
    assert len(result.proforma_statements.periods) == 2
