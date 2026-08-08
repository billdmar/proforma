"""Real-deal (Synopsys/ANSYS) flagship bundle — integration + invariant tests.

Builds the actual `MergerModelBundle` from cached SEC facts + the orchestrator's
assumptions (docs/ASSUMPTIONS.md §3) and asserts the disclosed terms flow
through, every deal invariant holds, the pre-close base year is used (NOT the
post-close SNPS FY2025 that already consolidates ANSYS), and the
accretion/dilution signs are economically correct. Offline: reads only committed
fixtures.
"""

from __future__ import annotations

import pytest
from src.flagship import build_flagship_bundle
from src.schema import LineItem
from src.verify.invariants import run_all

_PRECEDENTS = "data/curated/precedents_software.csv"


@pytest.fixture(scope="module")
def bundle():
    return build_flagship_bundle(precedents_csv=_PRECEDENTS)


def test_disclosed_terms_flow_through(bundle):
    """The disclosed consideration ($197 cash + 0.3450 share, ~$390 implied,
    ~29% premium, ~87.3M target shares → ~30.1M new SNPS shares) reaches the
    consideration build unchanged."""
    c = bundle.deal.consideration
    assert c.cash_per_share == pytest.approx(197.00)
    assert bundle.terms.exchange_ratio.value == pytest.approx(0.3450)
    assert c.total_per_share == pytest.approx(390.19, abs=0.5)
    assert c.new_shares_issued == pytest.approx(0.3450 * c.target_shares, rel=1e-9)
    assert c.new_shares_issued / 1e6 == pytest.approx(30.1, abs=0.5)
    assert c.implied_premium_pct == pytest.approx(0.287, abs=0.01)


def test_pre_close_base_year_used(bundle):
    """Acquirer standalone base is Synopsys FY2024 (2024-10-31), NOT the
    post-close FY2025 (2025-10-31) that already consolidates ANSYS. A regression
    guard against double-counting the target."""
    aq = bundle.acquirer_statements
    base_end = aq.periods[aq.n_hist - 1].end
    assert base_end.year == 2024
    assert base_end.month == 10  # SNPS fiscal year ends Oct 31
    tgt = bundle.target_statements
    assert tgt.periods[tgt.n_hist - 1].end.year == 2024


def test_all_deal_invariants_green(bundle):
    """sources=uses, goodwill ties PPA, pro forma BS balances every period,
    EPS bridge recompute, contribution ties, synergy phase-in — both cases."""
    report = run_all(bundle)
    assert report.passed, report.summary()


def test_sources_equal_uses_no_residual_plug(bundle):
    """Financing is tuned so sources=uses with no 'additional_cash' plug (the
    plug would otherwise leave the pro forma BS off by its amount)."""
    su = bundle.deal.sources_and_uses
    assert su.balances()
    assert su.sources.get("additional_cash", 0.0) == pytest.approx(0.0, abs=1.0)


def test_goodwill_is_large_and_ties(bundle):
    """Software deal at a premium → large goodwill; it ties to the PPA walk and
    lands in the neighborhood of the actual post-close SNPS goodwill (~$26.9B),
    a directional reality check (our $8B intangible step-up is conservative)."""
    ppa = bundle.deal.ppa
    assert ppa.ties()
    assert 15e9 < ppa.goodwill < 30e9


def test_accretion_dilution_signs(bundle):
    """The deal is GAAP-dilutive (large step-up amortization on an all-premium
    software target) and more synergies ⇒ less dilutive (monotonic)."""
    base = next(c for c in bundle.combinations if "Base" in c.synergy_case.name)
    cons = next(c for c in bundle.combinations if "Conservative" in c.synergy_case.name)
    base_ad = base.accretion_by_year()
    cons_ad = cons.accretion_by_year()
    # Dilutive Year 1 in both cases (defensible; the GAAP-vs-non-GAAP story).
    assert base_ad[0] < 0
    assert cons_ad[0] < 0
    # More synergies (Base $300M) is less dilutive than Conservative ($150M) each year.
    for b, c in zip(base_ad, cons_ad, strict=True):
        assert b > c


def test_two_synergy_cases_both_ours(bundle):
    """Both synergy cases are OURS — the proxy quantifies none, so neither is
    flagged as management-disclosed."""
    assert len(bundle.combinations) == 2
    for combo in bundle.combinations:
        assert combo.synergy_case.is_disclosed is False


def test_precedents_and_fairness_loaded(bundle):
    """The curated precedents and the Qatalyst fairness disclosure are attached."""
    assert len(bundle.precedents) >= 6
    assert any("VMware" in p.target or "Figma" in p.target for p in bundle.precedents)
    assert len(bundle.fairness_disclosures) == 1
    assert bundle.fairness_disclosures[0].advisor == "Qatalyst Partners"


def test_determinism(bundle):
    """A second independent build reproduces identical headline numbers."""
    b2 = build_flagship_bundle(precedents_csv=_PRECEDENTS)
    assert bundle.deal.ppa.goodwill == b2.deal.ppa.goodwill
    assert (
        bundle.primary_combination().eps_bridge[0].pro_forma_eps
        == b2.primary_combination().eps_bridge[0].pro_forma_eps
    )


def test_projected_balance_sheets_balance_directly(bundle):
    """Independent spot-check of A = L + E on the raw pro forma series."""
    for combo in bundle.combinations:
        pf = combo.proforma_statements
        for j in range(len(pf.periods)):
            ta = pf.series(LineItem.TOTAL_ASSETS)[j]
            tl = pf.series(LineItem.TOTAL_LIABILITIES)[j]
            te = pf.series(LineItem.TOTAL_EQUITY)[j]
            assert abs(ta - (tl + te)) < 1.0
