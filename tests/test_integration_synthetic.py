"""G1 integration gate — the synthetic fixture deal, end-to-end and offline.

THE HEART OF G1. Two INVENTED companies — ``BigCo`` (acquirer) and ``SmallCo``
(target) — are given small, round, hand-checkable historicals. The FULL pipeline
runs on them:

    hand-built historical StatementSet
      → ThreeStatementBuilder.project        (linked 3-statement projection)
      → DealEngineImpl.build                 (consideration, S&U, PPA → goodwill)
      → CombinationEngine.combine            (pro forma IS/BS, EPS bridge, A/D)
      → MergerModelBundle
      → ExcelWorkbookWriter.write            (live-formula .xlsx)
      → recalc with the ``formulas`` library → diff build_verifier_cell_map to the cent
      → run_all deal invariants              (the Task-2 runner)

Every asserted headline number is derived by hand in ``test_headline_numbers``'s
docstring so the mechanics are pinned, not merely reproduced — no real-deal
output depends on any of this.

Deal shape:
    The primary synthetic deal is funded entirely with acquirer stock (exchange
    ratio, no cash / new debt / balance-sheet cash) so every number is
    hand-checkable with no financing circularity. A SECOND scenario
    (``test_financed_deal_differential_to_the_cent``) funds the same combination
    with new debt AND balance-sheet cash, exercising the interest legs, and
    proves the workbook↔engine differential still holds to the cent on a
    financed deal — the check that closed the G1 interest-leg finding (the EPS
    bridge now stores all four adjustment legs after-tax, so the engine's pro
    forma NI and the workbook formula agree by construction).

The target pays out 100% of net income each projected year, holding its book
equity flat — the condition under which the combination engine's static day-1
purchase-accounting adjustments keep the pro forma balance sheet balanced every
period (see the CombinationEngine docstring: it balances "whenever sources =
uses and the target's book equity ties to its reported total equity").
"""

from __future__ import annotations

import os
from datetime import date

import formulas
import pytest
from src.combine import CombinationEngine
from src.deal import DealEngineImpl
from src.interfaces import (
    DealAssumptions,
    MergerModelBundle,
    ProjectionAssumptions,
    StatementSet,
    SynergyCase,
)
from src.schema import (
    CompanyMeta,
    ConsiderationType,
    DealTerms,
    DocProvenance,
    LineItem,
    Period,
    PeriodType,
    SourcedValue,
)
from src.standalone import ThreeStatementBuilder
from src.verify.invariants import run_all
from src.workbook import ExcelWorkbookWriter, build_verifier_cell_map

# --------------------------------------------------------------------------- #
# hand-built inputs (we own every number)
# --------------------------------------------------------------------------- #
_PROV = DocProvenance(
    accession="0000000000-24-000000", form="DEFM14A", filed=date(2024, 3, 1), section="Synthetic"
)


def _dur(y: int) -> Period:
    return Period(PeriodType.DURATION, end=date(y, 12, 31), start=date(y, 1, 1), fy=y, fp="FY")


def _sv(v: float, unit: str = "USD/share") -> SourcedValue:
    return SourcedValue(value=v, provenance=_PROV, unit=unit)


def _historical(
    *,
    rev: float,
    cor: float,
    cash: float,
    ar: float,
    inv: float,
    ppe: float,
    gw: float,
    ap: float,
    std: float,
    ltd: float,
    cs: float,
    re: float,
    shares: float,
) -> StatementSet:
    """One balancing historical fiscal year (FY2024). Totals are summed from the
    components so TA = TL + TE holds by construction (round numbers)."""
    rows: dict[LineItem, list[float | None]] = {li: [None] for li in LineItem}
    rows[LineItem.REVENUE] = [rev]
    rows[LineItem.COST_OF_REVENUE] = [cor]
    rows[LineItem.GROSS_PROFIT] = [rev - cor]
    rows[LineItem.CASH] = [cash]
    rows[LineItem.ACCOUNTS_RECEIVABLE] = [ar]
    rows[LineItem.INVENTORY] = [inv]
    rows[LineItem.PPE_NET] = [ppe]
    rows[LineItem.GOODWILL] = [gw]
    rows[LineItem.TOTAL_ASSETS] = [cash + ar + inv + ppe + gw]
    rows[LineItem.ACCOUNTS_PAYABLE] = [ap]
    rows[LineItem.SHORT_TERM_DEBT] = [std]
    rows[LineItem.LONG_TERM_DEBT] = [ltd]
    rows[LineItem.TOTAL_LIABILITIES] = [ap + std + ltd]
    rows[LineItem.COMMON_STOCK] = [cs]
    rows[LineItem.RETAINED_EARNINGS] = [re]
    rows[LineItem.TOTAL_EQUITY] = [cs + re]
    rows[LineItem.SHARES_DILUTED] = [shares]
    rows[LineItem.SHARES_OUTSTANDING] = [shares]
    return StatementSet(periods=[_dur(2024)], rows=rows, n_hist=1)


def _assumptions(growth: float, payout: float) -> ProjectionAssumptions:
    """Flat drivers; no interest (all-stock deal has no financing circularity)."""
    return ProjectionAssumptions(
        n_years=3,
        revenue_growth=[growth] * 3,
        gross_margin=[0.60] * 3,
        sga_pct_revenue=[0.20] * 3,
        rnd_pct_revenue=[0.10] * 3,
        dso=[30] * 3,
        dio=[30] * 3,
        dpo=[30] * 3,
        capex_pct_revenue=[0.05] * 3,
        da_pct_revenue=[0.05] * 3,
        tax_rate=[0.25] * 3,
        interest_rate_on_debt=0.0,
        interest_rate_on_cash=0.0,
        min_cash=0.0,
        dividend_payout=[payout] * 3,
    )


# Constants for the synthetic deal (round, hand-checkable).
_ACQ_DILUTED_SHARES = 1000.0
_TGT_DILUTED_SHARES = 400.0
_EXCHANGE_RATIO = 0.5
_REFERENCE_PRICE = 100.0
_TARGET_SHARES = 400.0
_PREMIUM_REF = 40.0
_TAX = 0.25


def _build_bundle(
    *,
    new_debt: float = 0.0,
    new_debt_rate: float = 0.0,
    cash_on_hand_used: float = 0.0,
    foregone_cash_yield: float = 0.0,
) -> MergerModelBundle:
    """Build the synthetic BigCo/SmallCo bundle. Defaults give the all-stock
    deal; passing financing legs produces the debt-/cash-funded variant that
    exercises the after-tax interest legs in the differential."""
    builder = ThreeStatementBuilder()

    # Acquirer retains all earnings (0% payout); target pays out 100% so its book
    # equity stays flat across the horizon (the BS-balancing condition).
    acq = builder.project(
        _historical(
            rev=10000.0,
            cor=4000.0,
            cash=2000.0,
            ar=1000.0,
            inv=500.0,
            ppe=1500.0,
            gw=400.0,
            ap=600.0,
            std=800.0,
            ltd=1000.0,
            cs=2000.0,
            re=1000.0,
            shares=_ACQ_DILUTED_SHARES,
        ),
        _assumptions(growth=0.10, payout=0.0),
    )
    tgt = builder.project(
        _historical(
            rev=4000.0,
            cor=1600.0,
            cash=800.0,
            ar=400.0,
            inv=200.0,
            ppe=1200.0,
            gw=900.0,
            ap=200.0,
            std=300.0,
            ltd=800.0,
            cs=1000.0,
            re=1200.0,
            shares=_TGT_DILUTED_SHARES,
        ),
        _assumptions(growth=0.05, payout=1.0),
    )
    # The standalone builder does not drive diluted shares in the projection
    # (an honest unknown it leaves None); the flagship pipeline sets them from
    # the share plan. Here we inject a flat diluted-share count so the pro forma
    # EPS build has real denominators.
    for stmts, sh in ((acq, _ACQ_DILUTED_SHARES), (tgt, _TGT_DILUTED_SHARES)):
        n = stmts.n_hist
        stmts.rows[LineItem.SHARES_DILUTED] = stmts.rows[LineItem.SHARES_DILUTED][:n] + [sh] * (
            len(stmts.periods) - n
        )

    # Target book equity / existing goodwill for the PPA come from its balance
    # sheet at the combination point (flat, so any projected year is the same).
    tgt_book_eq = tgt.series(LineItem.TOTAL_EQUITY)[tgt.n_hist]
    tgt_existing_gw = tgt.series(LineItem.GOODWILL)[tgt.n_hist]

    terms = DealTerms(
        acquirer_ticker="BIG",
        target_ticker="SML",
        acquirer_name="BigCo",
        target_name="SmallCo",
        announce_date=date(2024, 1, 1),
        close_date=None,
        consideration_type=ConsiderationType.STOCK,
        exchange_ratio=_sv(_EXCHANGE_RATIO, "ratio"),
        reference_acquirer_price=_sv(_REFERENCE_PRICE),
        target_shares_outstanding=_sv(_TARGET_SHARES, "shares"),
        premium_reference_price=_sv(_PREMIUM_REF),
    )
    da = DealAssumptions(
        new_debt=new_debt,
        new_debt_rate=new_debt_rate,
        cash_on_hand_used=cash_on_hand_used,
        foregone_cash_yield=foregone_cash_yield,
        advisory_fees=0.0,
        financing_fees=0.0,
        intangible_step_up=5000.0,
        intangible_useful_life_years=10.0,
        ppe_step_up=1000.0,
        ppe_useful_life_years=5.0,
        deferred_tax_rate=_TAX,
        marginal_tax_rate=_TAX,
    )
    deal = DealEngineImpl().build(
        terms, da, target_book_equity=tgt_book_eq, target_existing_goodwill=tgt_existing_gw
    )

    engine = CombinationEngine()
    mgmt = engine.combine(
        acq,
        tgt,
        deal,
        da,
        SynergyCase(
            name="Management", run_rate_annual=400.0, phase_in=[0.5, 0.75, 1.0], is_disclosed=True
        ),
    )
    ours = engine.combine(
        acq,
        tgt,
        deal,
        da,
        SynergyCase(name="Conservative", run_rate_annual=250.0, phase_in=[0.4, 0.7, 1.0]),
    )

    return MergerModelBundle(
        acquirer=CompanyMeta(cik="0000000001", ticker="BIG", name="BigCo"),
        target=CompanyMeta(cik="0000000002", ticker="SML", name="SmallCo"),
        terms=terms,
        acquirer_statements=acq,
        target_statements=tgt,
        acquirer_assumptions=_assumptions(0.10, 0.0),
        target_assumptions=_assumptions(0.05, 1.0),
        deal_assumptions=da,
        deal=deal,
        combinations=[mgmt, ours],
    )


# --------------------------------------------------------------------------- #
# module-scoped bundle (built once; the pipeline is deterministic)
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def bundle() -> MergerModelBundle:
    return _build_bundle()


# --------------------------------------------------------------------------- #
# hand-computed headline numbers (pinned to the cent)
# --------------------------------------------------------------------------- #
def test_headline_numbers(bundle: MergerModelBundle):
    """Every number here is derived by hand.

    Consideration (all-stock, exchange ratio 0.5, reference price 100, 400 target
    shares):
        stock value / target share = 0.5 × 100 = 50.00
        equity purchase price = 50 × 400 = 20,000
        new shares issued = 0.5 × 400 = 200
        implied premium = 50 / 40 − 1 = +25.0%

    PPA → goodwill (target book equity 2,200, existing goodwill 900 written off;
    intangible step-up 5,000, PP&E step-up 1,000, DTL rate 25%):
        identifiable net assets at book = 2,200 − 900 = 1,300
        DTL = 25% × (5,000 + 1,000) = 1,500
        net identifiable assets = 1,300 + 5,000 + 1,000 − 1,500 = 5,800
        goodwill = 20,000 − 5,800 = 14,200

    Standalone Year-1 net income (tax 25%, no interest):
        Acquirer: rev 10,000×1.10 = 11,000; COGS 40% = 4,400; gross 6,600;
            SG&A 20% = 2,200; R&D 10% = 1,100; EBIT 3,300; tax 825; NI = 2,475
        Target:   rev 4,000×1.05 = 4,200; COGS 1,680; gross 2,520; SG&A 840;
            R&D 420; EBIT 1,260; tax 315; NI = 945

    Year-1 pro forma (Management case), incremental step-up D&A = 5,000/10 +
    1,000/5 = 700 pre-tax → 525 after-tax; synergies 400×0.5 = 200 pre-tax → 150
    after-tax; no interest legs:
        pro forma NI = 2,475 + 945 − 525 + 150 = 3,045
        pro forma shares = 1,000 + 200 = 1,200
        pro forma EPS = 3,045 / 1,200 = 2.5375
        acquirer standalone EPS = 2,475 / 1,000 = 2.475
        Year-1 accretion = 2.5375 / 2.475 − 1 = +2.5253%
    """
    cons = bundle.deal.consideration
    ppa = bundle.deal.ppa
    assert cons.equity_purchase_price == pytest.approx(20_000.0)
    assert cons.new_shares_issued == pytest.approx(200.0)
    assert cons.implied_premium_pct == pytest.approx(0.25)
    assert ppa.deferred_tax_liability == pytest.approx(1_500.0)
    assert ppa.net_identifiable_assets == pytest.approx(5_800.0)
    assert ppa.goodwill == pytest.approx(14_200.0)

    mgmt = bundle.primary_combination()
    b1 = mgmt.eps_bridge[0]
    assert b1.acquirer_standalone_ni == pytest.approx(2_475.0)
    assert b1.target_standalone_ni == pytest.approx(945.0)
    assert b1.pro_forma_net_income == pytest.approx(3_045.0)
    assert b1.pro_forma_shares == pytest.approx(1_200.0)
    assert b1.pro_forma_eps == pytest.approx(2.5375)
    assert b1.acquirer_standalone_eps == pytest.approx(2.475)
    assert b1.accretion_dilution_pct == pytest.approx(0.0252525, abs=1e-6)


# --------------------------------------------------------------------------- #
# the differential — recalc the workbook and diff to the cent (the moat)
# --------------------------------------------------------------------------- #
def test_excel_python_differential_to_the_cent(bundle: MergerModelBundle, tmp_path):
    """Write the live-formula workbook, recalc it with the ``formulas`` library,
    and assert EVERY mapped cell reproduces the engine value to the cent."""
    p = tmp_path / "synthetic_model.xlsx"
    ExcelWorkbookWriter().write(str(p), bundle)

    cell_map = build_verifier_cell_map(bundle)
    assert len(cell_map) >= 20, "expected a broad differential surface"

    sol = formulas.ExcelModel().loads(str(p)).finish().calculate()
    fname = os.path.basename(str(p))
    mismatches = []
    for (sheet, coord), engine_value in cell_map.items():
        node = sol.get(f"'[{fname}]{sheet.upper()}'!{coord}")
        wb_value = None if node is None else float(node.value[0, 0])
        if wb_value is None or abs(wb_value - engine_value) > 0.01:
            mismatches.append((sheet, coord, engine_value, wb_value))
    assert not mismatches, f"differential mismatches: {mismatches}"


def test_financed_deal_differential_to_the_cent(tmp_path):
    """The same combination, funded with new debt (2,000 @ 5%) and balance-sheet
    cash (1,000 @ 3% foregone yield), so the interest legs are NON-zero:
        incremental interest  = 2,000 × 0.05 = 100 pre-tax → 75 after-tax
        foregone cash yield   = 1,000 × 0.03 = 30 pre-tax  → 22.5 after-tax
    The EPS bridge stores both legs after-tax, and the workbook's pro forma NI
    formula subtracts those same after-tax cells — so the recalculated workbook
    must still match the engine to the cent. This is the check that would have
    caught (and now guards against a regression of) the interest-leg tax seam.
    """
    financed = _build_bundle(
        new_debt=2000.0, new_debt_rate=0.05, cash_on_hand_used=1000.0, foregone_cash_yield=0.03
    )
    b1 = financed.primary_combination().eps_bridge[0]
    assert b1.incremental_interest_aftertax == pytest.approx(75.0)  # 100 × (1 − 0.25)
    assert b1.foregone_interest_aftertax == pytest.approx(22.5)  # 30 × (1 − 0.25)

    p = tmp_path / "financed_model.xlsx"
    ExcelWorkbookWriter().write(str(p), financed)
    cell_map = build_verifier_cell_map(financed)
    sol = formulas.ExcelModel().loads(str(p)).finish().calculate()
    fname = os.path.basename(str(p))
    mismatches = []
    for (sheet, coord), engine_value in cell_map.items():
        node = sol.get(f"'[{fname}]{sheet.upper()}'!{coord}")
        wb_value = None if node is None else float(node.value[0, 0])
        if wb_value is None or abs(wb_value - engine_value) > 0.01:
            mismatches.append((sheet, coord, engine_value, wb_value))
    assert not mismatches, f"financed-deal differential mismatches: {mismatches}"


# --------------------------------------------------------------------------- #
# all deal invariants green (the Task-2 runner)
# --------------------------------------------------------------------------- #
def test_all_deal_invariants_green(bundle: MergerModelBundle):
    """sources = uses, goodwill plug, pro forma BS balances every period, EPS
    bridge recompute, contribution ties, synergy phase-in — for BOTH cases."""
    report = run_all(bundle)
    assert report.passed, report.summary()
    # 2 deal-level + 4 checks × 2 synergy cases = 10 results.
    assert len(report.results) == 10


def test_pro_forma_balance_sheet_balances_each_period(bundle: MergerModelBundle):
    """Independent spot-check of the BS identity on the raw pro forma series."""
    for combo in bundle.combinations:
        pf = combo.proforma_statements
        for j in range(len(pf.periods)):
            ta = pf.series(LineItem.TOTAL_ASSETS)[j]
            tl = pf.series(LineItem.TOTAL_LIABILITIES)[j]
            te = pf.series(LineItem.TOTAL_EQUITY)[j]
            assert abs(ta - (tl + te)) < 1.0, f"{combo.synergy_case.name} period {j}"


def test_sensitivity_sign_more_synergies_more_accretive(bundle: MergerModelBundle):
    """Sanity: the Management case (400 run-rate) is more accretive every year
    than the Conservative case (250 run-rate) — synergies up ⇒ more accretive."""
    mgmt = next(c for c in bundle.combinations if c.synergy_case.name == "Management")
    cons = next(c for c in bundle.combinations if c.synergy_case.name == "Conservative")
    for m, c in zip(mgmt.accretion_by_year(), cons.accretion_by_year(), strict=True):
        assert m > c


def test_pipeline_is_deterministic():
    """Full rebuild from the hand-built inputs reproduces identical headline
    numbers (DoD #7 determinism, at the engine level)."""
    b1 = _build_bundle()
    b2 = _build_bundle()
    assert b1.deal.ppa.goodwill == b2.deal.ppa.goodwill
    assert (
        b1.primary_combination().eps_bridge[0].pro_forma_eps
        == b2.primary_combination().eps_bridge[0].pro_forma_eps
    )
