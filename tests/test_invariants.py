"""Tests for the deal-invariant runner (``src.verify.invariants``).

Each check is exercised on a hand-built input (we own the inputs; no engine is
run here — the end-to-end machinery is proved in test_integration_synthetic.py)
in both a passing and a failing configuration, so the runner is a genuine second
opinion rather than a rubber stamp. Every asserted residual is hand-derivable.
"""

from __future__ import annotations

from datetime import date

import pytest
from src.interfaces import (
    CombinationResult,
    Consideration,
    ContributionAnalysis,
    DealAssumptions,
    DealResult,
    EPSBridge,
    MergerModelBundle,
    ProjectionAssumptions,
    PurchasePriceAllocation,
    SourcesAndUses,
    StatementSet,
    SynergyCase,
)
from src.schema import (
    CompanyMeta,
    ConsiderationType,
    DealTerms,
    LineItem,
    Period,
    PeriodType,
)
from src.verify.invariants import (
    check_contribution_ties,
    check_eps_bridge_recompute,
    check_goodwill_ties,
    check_pro_forma_balance_sheet,
    check_sources_equal_uses,
    check_synergy_phase_in,
    run_all,
)


def _dur(y: int) -> Period:
    return Period(PeriodType.DURATION, end=date(y, 12, 31), start=date(y, 1, 1), fy=y, fp="FY")


# --------------------------------------------------------------------------- #
# sources = uses
# --------------------------------------------------------------------------- #
def _deal_with_su(sources: dict[str, float], uses: dict[str, float]) -> DealResult:
    return DealResult(
        consideration=Consideration(
            cash_per_share=0.0,
            stock_per_share_value=0.0,
            total_per_share=0.0,
            target_shares=0.0,
            aggregate_cash=0.0,
            aggregate_stock_value=0.0,
            equity_purchase_price=0.0,
        ),
        sources_and_uses=SourcesAndUses(sources=sources, uses=uses),
        ppa=PurchasePriceAllocation(
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


def test_sources_equal_uses_pass_and_fail():
    ok = _deal_with_su({"debt": 600.0, "cash": 400.0}, {"price": 1000.0})
    assert check_sources_equal_uses(ok).ok

    bad = _deal_with_su({"debt": 600.0}, {"price": 1000.0})
    r = check_sources_equal_uses(bad)
    assert not r.ok
    assert r.residuals == [-400.0]  # sources − uses


# --------------------------------------------------------------------------- #
# goodwill ties
# --------------------------------------------------------------------------- #
def _deal_with_ppa(eqpp: float, net_ident: float, goodwill: float) -> DealResult:
    d = _deal_with_su({}, {})
    d.ppa = PurchasePriceAllocation(
        equity_purchase_price=eqpp,
        target_book_equity=0.0,
        target_existing_goodwill=0.0,
        identifiable_net_assets_at_book=0.0,
        intangible_step_up=0.0,
        ppe_step_up=0.0,
        deferred_tax_liability=0.0,
        net_identifiable_assets=net_ident,
        goodwill=goodwill,
    )
    return d


def test_goodwill_ties_pass_and_fail():
    ok = _deal_with_ppa(eqpp=1000.0, net_ident=300.0, goodwill=700.0)
    assert check_goodwill_ties(ok).ok

    bad = _deal_with_ppa(eqpp=1000.0, net_ident=300.0, goodwill=650.0)
    r = check_goodwill_ties(bad)
    assert not r.ok
    assert r.residuals == [pytest.approx(-50.0)]  # 650 − (1000 − 300)


# --------------------------------------------------------------------------- #
# pro forma balance sheet balances
# --------------------------------------------------------------------------- #
def _bs(ta: list[float], tl: list[float], te: list[float]) -> StatementSet:
    n = len(ta)
    return StatementSet(
        periods=[_dur(2025 + j) for j in range(n)],
        rows={
            LineItem.TOTAL_ASSETS: list(ta),
            LineItem.TOTAL_LIABILITIES: list(tl),
            LineItem.TOTAL_EQUITY: list(te),
        },
        n_hist=0,
    )


def test_pro_forma_balance_sheet_pass_and_fail():
    combo_ok = _bs([5000.0, 5200.0], [2000.0, 2100.0], [3000.0, 3100.0])
    r = check_pro_forma_balance_sheet(combo_ok, label="mgmt")
    assert r.ok
    assert r.name == "pro_forma_balance_sheet[mgmt]"

    combo_bad = _bs([5000.0], [2000.0], [2990.0])  # off by 10
    rb = check_pro_forma_balance_sheet(combo_bad)
    assert not rb.ok
    assert rb.residuals == [pytest.approx(10.0)]


# --------------------------------------------------------------------------- #
# EPS bridge recompute
# --------------------------------------------------------------------------- #
def _bridge(*, pf_eps: float, pf_ni: float, shares: float) -> EPSBridge:
    """A one-year bridge; all four adjustment legs are stored after-tax
    (200 interest + 48 foregone + 40 D&A − 80 synergies), so pro forma NI is a
    pure additive walk from the two standalone net incomes."""
    return EPSBridge(
        year=_dur(2025),
        acquirer_standalone_ni=1000.0,
        target_standalone_ni=400.0,
        incremental_interest_aftertax=200.0,
        foregone_interest_aftertax=48.0,
        incremental_da_aftertax=40.0,
        synergies_aftertax=80.0,
        pro_forma_net_income=pf_ni,
        acquirer_standalone_shares=100.0,
        new_shares_issued=25.0,
        pro_forma_shares=shares,
        acquirer_standalone_eps=10.0,
        pro_forma_eps=pf_eps,
    )


def _combo_with_bridge(b: EPSBridge, case: SynergyCase | None = None) -> CombinationResult:
    return CombinationResult(
        synergy_case=case or SynergyCase(name="none", run_rate_annual=0.0, phase_in=[0.0]),
        proforma_statements=StatementSet(periods=[_dur(2025)], rows={}, n_hist=0),
        eps_bridge=[b],
        contribution=ContributionAnalysis(
            acquirer_revenue=0.0,
            target_revenue=0.0,
            acquirer_ebitda=0.0,
            target_ebitda=0.0,
            acquirer_net_income=0.0,
            target_net_income=0.0,
            acquirer_ownership_pct=0.8,
            target_ownership_pct=0.2,
        ),
    )


def test_eps_bridge_recompute_pass_and_fail():
    # All legs after-tax → additive walk: NI = 1000+400 − 200 − 48 − 40 + 80 = 1192; /125 = 9.536.
    ni = 1000.0 + 400.0 - 200.0 - 48.0 - 40.0 + 80.0
    eps = ni / 125.0
    ok = _combo_with_bridge(_bridge(pf_eps=eps, pf_ni=ni, shares=125.0))
    assert check_eps_bridge_recompute(ok, tax_rate=0.20).ok

    # Corrupt the reported EPS → the recompute catches it.
    bad = _combo_with_bridge(_bridge(pf_eps=eps + 1.0, pf_ni=ni, shares=125.0))
    r = check_eps_bridge_recompute(bad, tax_rate=0.20)
    assert not r.ok
    assert r.residuals[0] == pytest.approx(-1.0)


# --------------------------------------------------------------------------- #
# contribution ties (ownership sums to 1.0)
# --------------------------------------------------------------------------- #
def test_contribution_ties_pass_and_fail():
    ok = _combo_with_bridge(_bridge(pf_eps=1.0, pf_ni=125.0, shares=125.0))
    assert check_contribution_ties(ok).ok

    bad = _combo_with_bridge(_bridge(pf_eps=1.0, pf_ni=125.0, shares=125.0))
    bad.contribution.target_ownership_pct = 0.25  # 0.8 + 0.25 = 1.05
    r = check_contribution_ties(bad)
    assert not r.ok
    assert r.residuals[0] == pytest.approx(0.05)


# --------------------------------------------------------------------------- #
# synergy phase-in
# --------------------------------------------------------------------------- #
def test_synergy_phase_in_pass_and_fail():
    case = SynergyCase(name="mgmt", run_rate_annual=500.0, phase_in=[0.25, 0.5, 1.0])
    # after-tax realized at t=20%: 100, 200, 400.
    bridges = []
    for j, at in enumerate((100.0, 200.0, 400.0)):
        b = _bridge(pf_eps=1.0, pf_ni=1.0, shares=1.0)
        b.synergies_aftertax = at
        b.year = _dur(2025 + j)
        bridges.append(b)
    combo = CombinationResult(
        synergy_case=case,
        proforma_statements=StatementSet(periods=[_dur(2025)], rows={}, n_hist=0),
        eps_bridge=bridges,
        contribution=_combo_with_bridge(bridges[0]).contribution,
    )
    assert check_synergy_phase_in(combo, tax_rate=0.20).ok

    # Corrupt year-2 realized synergy → caught.
    combo.eps_bridge[1].synergies_aftertax = 250.0
    r = check_synergy_phase_in(combo, tax_rate=0.20)
    assert not r.ok
    assert r.residuals[1] == pytest.approx(50.0)  # 250 − 200


# --------------------------------------------------------------------------- #
# run_all over a bundle
# --------------------------------------------------------------------------- #
def _minimal_bundle() -> MergerModelBundle:
    """A tiny but fully self-consistent bundle so run_all exercises the deal-level
    checks once plus the combination checks per case."""
    acquirer = CompanyMeta(cik="1", ticker="A", name="A")
    target = CompanyMeta(cik="2", ticker="B", name="B")
    terms = DealTerms(
        acquirer_ticker="A",
        target_ticker="B",
        acquirer_name="A",
        target_name="B",
        announce_date=date(2025, 1, 1),
        close_date=None,
        consideration_type=ConsiderationType.STOCK,
    )
    deal = _deal_with_ppa(eqpp=1000.0, net_ident=300.0, goodwill=700.0)
    deal.sources_and_uses = SourcesAndUses(sources={"stock": 1000.0}, uses={"price": 1000.0})

    case = SynergyCase(name="mgmt", run_rate_annual=0.0, phase_in=[0.0], is_disclosed=True)
    # After-tax legs (200 interest + 48 foregone + 40 D&A), no synergies here.
    ni = 1000.0 + 400.0 - 200.0 - 48.0 - 40.0 + 0.0
    b = _bridge(pf_eps=ni / 125.0, pf_ni=ni, shares=125.0)
    b.synergies_aftertax = 0.0
    combo = CombinationResult(
        synergy_case=case,
        proforma_statements=_bs([5000.0], [2000.0], [3000.0]),
        eps_bridge=[b],
        contribution=_combo_with_bridge(b).contribution,
    )
    empty = StatementSet(periods=[_dur(2025)], rows={}, n_hist=0)
    return MergerModelBundle(
        acquirer=acquirer,
        target=target,
        terms=terms,
        acquirer_statements=empty,
        target_statements=empty,
        acquirer_assumptions=ProjectionAssumptions(),
        target_assumptions=ProjectionAssumptions(),
        deal_assumptions=DealAssumptions(marginal_tax_rate=0.20),
        deal=deal,
        combinations=[combo],
    )


def test_run_all_passes_on_consistent_bundle():
    report = run_all(_minimal_bundle())
    assert report.passed, report.summary()
    # 2 deal-level + 4 per combination case = 6 results.
    assert len(report.results) == 6
    assert "OK" in report.summary()


def test_run_all_reports_failure_on_broken_goodwill():
    bundle = _minimal_bundle()
    bundle.deal.ppa.goodwill += 123.0  # break the PPA plug
    report = run_all(bundle)
    assert not report.passed
    assert "FAIL" in report.summary()
