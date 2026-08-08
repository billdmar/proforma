"""Deal #2 (Cisco/Splunk) flagship bundle — integration + invariant tests.

The P6 generality proof: the SAME engines that build Synopsys/ANSYS build a
deliberately different-shaped deal — all-cash (no stock leg, zero new shares),
a loss-making, negative-book-equity target, two fairness advisors. Asserts the
disclosed terms flow through, every deal invariant holds, the pre-close base
year is used (Cisco FY2023, NOT the post-close FY2024/25 that already
consolidate Splunk), and the accretion/dilution is (honestly) dilutive and
monotone in synergies. Offline: reads only committed fixtures.
"""

from __future__ import annotations

import pytest
from src.flagship_csco_splk import build_flagship_bundle
from src.narrative_csco_splk import CSCO_SPLK_NARRATIVE
from src.schema import ConsiderationType, LineItem
from src.verify.invariants import run_all

_PRECEDENTS = "data/curated/precedents_software.csv"


@pytest.fixture(scope="module")
def bundle():
    return build_flagship_bundle(precedents_csv=_PRECEDENTS)


def test_disclosed_terms_flow_through(bundle):
    """The disclosed consideration ($157.00 all cash, ~31% premium, ~168.5M
    target shares, all-cash ⇒ zero new Cisco shares) reaches the consideration
    build unchanged."""
    c = bundle.deal.consideration
    assert c.cash_per_share == pytest.approx(157.00)
    assert bundle.terms.consideration_type is ConsiderationType.CASH
    # All-cash: no stock leg disclosed.
    assert bundle.terms.exchange_ratio is None
    assert c.total_per_share == pytest.approx(157.00)
    assert c.stock_per_share_value == pytest.approx(0.0)
    assert c.new_shares_issued == pytest.approx(0.0)
    assert c.target_shares == pytest.approx(168_536_732.0)
    # ~31% premium over the $119.59 unaffected close (engine computes ~31.3%).
    assert c.implied_premium_pct == pytest.approx(0.313, abs=0.01)


def test_pre_close_base_year_used(bundle):
    """Acquirer standalone base is Cisco FY2023 (2023-07-29), NOT the post-close
    FY2024/FY2025 that already consolidate Splunk (goodwill jumps to ~$58.7B). A
    regression guard against double-counting the target."""
    aq = bundle.acquirer_statements
    base_end = aq.periods[aq.n_hist - 1].end
    assert base_end.year == 2023
    assert base_end.month == 7  # Cisco fiscal year ends late July
    tgt = bundle.target_statements
    tgt_end = tgt.periods[tgt.n_hist - 1].end
    assert tgt_end.year == 2023
    assert tgt_end.month == 1  # Splunk fiscal year ends Jan 31


def test_target_is_negative_book_equity(bundle):
    """Splunk's base-year book equity is negative (−$110.5M reported), carried
    as-is into the model — this is the loss-making-target stress the deal tests."""
    tgt = bundle.target_statements
    base_equity = tgt.series(LineItem.TOTAL_EQUITY)[tgt.n_hist - 1]
    assert base_equity is not None and base_equity < 0.0


def test_all_deal_invariants_green(bundle):
    """sources=uses, goodwill ties PPA, pro forma BS balances every period,
    EPS bridge recompute, contribution ties, synergy phase-in — both cases.
    The 100% target payout keeps target equity flat so the BS balances despite
    the negative base equity."""
    report = run_all(bundle)
    assert report.passed, report.summary()


def test_sources_equal_uses_no_residual_plug(bundle):
    """All-cash financing is tuned (cash on hand fills the exact remainder after
    the disclosed $22B debt) so sources=uses with no 'additional_cash' plug."""
    su = bundle.deal.sources_and_uses
    assert su.balances()
    assert su.sources.get("additional_cash", 0.0) == pytest.approx(0.0, abs=1.0)
    # All-cash: the stock-issued source is zero.
    assert su.sources.get("stock_issued", 0.0) == pytest.approx(0.0, abs=1.0)
    assert su.sources["new_debt"] == pytest.approx(22_000_000_000.0)


def test_goodwill_is_large_and_ties(bundle):
    """Negative-book-equity software target at a premium → large goodwill; it ties
    to the PPA walk. Almost the entire ~$26.5B price is intangibles + goodwill."""
    ppa = bundle.deal.ppa
    assert ppa.ties()
    assert ppa.goodwill > 15e9
    assert ppa.target_book_equity < 0.0  # negative equity carried into the PPA


def test_accretion_dilution_signs(bundle):
    """The all-cash deal for a loss-making target is heavily GAAP-dilutive early
    (step-up amortization + full-debt interest, no share-count offset), and more
    synergies ⇒ less dilutive (monotonic)."""
    base = next(c for c in bundle.combinations if "Base" in c.synergy_case.name)
    cons = next(c for c in bundle.combinations if "Conservative" in c.synergy_case.name)
    base_ad = base.accretion_by_year()
    cons_ad = cons.accretion_by_year()
    # Dilutive Year 1 in both cases (the honest all-cash / loss-making-target result).
    assert base_ad[0] < 0
    assert cons_ad[0] < 0
    # Dilution narrows over the horizon as Splunk's margin ramps (base case).
    assert base_ad[-1] > base_ad[0]
    # More synergies (Base $400M) is less dilutive than Conservative ($200M) each year.
    for b, c in zip(base_ad, cons_ad, strict=True):
        assert b > c


def test_two_synergy_cases_both_ours(bundle):
    """Both synergy cases are OURS — the proxy quantifies none, so neither is
    flagged as management-disclosed."""
    assert len(bundle.combinations) == 2
    for combo in bundle.combinations:
        assert combo.synergy_case.is_disclosed is False


def test_sensitivities_monotone_and_breakeven(bundle):
    """Premium×synergies grid is monotone (more premium ⇒ more dilutive; more
    synergies ⇒ more accretive) and the breakeven synergy run-rate is large and
    positive (this deal does not pay for itself on cost synergies)."""
    sens = bundle.sensitivities
    assert sens is not None
    grid = sens.premium_x_synergies
    # Non-increasing down each premium column (higher premium ⇒ more dilutive).
    for j in range(len(grid.col_values)):
        col = [grid.values[i][j] for i in range(len(grid.row_values))]
        for a, b in zip(col, col[1:], strict=False):
            assert b <= a + 1e-9
    # Non-decreasing across each synergy row (more synergies ⇒ more accretive).
    for row in grid.values:
        for a, b in zip(row, row[1:], strict=False):
            assert b >= a - 1e-9
    assert sens.breakeven_synergies is not None
    assert sens.breakeven_synergies > 1e9


def test_standalone_target_dcf(bundle):
    """The standalone Splunk DCF is attached and is a growth-DCF stress case:
    barely-profitable target ⇒ Gordon value below the exit-multiple value, both
    reported honestly (not tuned)."""
    dcf = bundle.target_dcf
    assert dcf is not None
    assert dcf.wacc == pytest.approx(0.103, abs=0.005)
    assert dcf.implied_price_gordon > 0.0
    assert dcf.implied_price_exit > dcf.implied_price_gordon


def test_precedents_and_two_advisors_loaded(bundle):
    """The curated software precedents and BOTH Splunk advisors are attached."""
    assert len(bundle.precedents) >= 6
    advisors = {fd.advisor for fd in bundle.fairness_disclosures}
    assert advisors == {"Qatalyst Partners", "Morgan Stanley"}


def test_fairness_reproduction_both_advisors(bundle):
    """The two-advisor fairness differential reproduces each advisor's DCF from
    its disclosed inputs, with quantified overlap; sub-analyses lacking a single
    reproducible assumption set report an honest None (never a tuned fit)."""
    fd = bundle.fairness_differential
    assert fd is not None
    for advisor in ("Qatalyst Partners", "Morgan Stanley"):
        reps = [r for r in fd.reproductions if r.advisor == advisor]
        assert reps, f"no reproductions for {advisor}"
        dcf = next(r for r in reps if r.method == "Discounted Cash Flow")
        # DCF is reproducible (disclosed discount-rate + perpetuity-growth bands).
        assert dcf.our_low is not None and dcf.our_high is not None
        assert dcf.overlap_pct is not None and dcf.overlap_pct > 0.0
        # Non-reproducible sub-analyses carry an honest None + a deviation note.
        for r in reps:
            if r.our_low is None:
                assert r.overlap_pct is None
                assert r.deviation_note
    # Mean overlap spans the reproducible set only.
    assert fd.mean_overlap is not None and 0.0 < fd.mean_overlap < 1.0


def test_determinism(bundle):
    """A second independent build reproduces identical headline numbers."""
    b2 = build_flagship_bundle(precedents_csv=_PRECEDENTS)
    assert bundle.deal.ppa.goodwill == b2.deal.ppa.goodwill
    assert (
        bundle.primary_combination().eps_bridge[0].pro_forma_eps
        == b2.primary_combination().eps_bridge[0].pro_forma_eps
    )
    assert bundle.target_dcf.implied_price_gordon == b2.target_dcf.implied_price_gordon
    assert bundle.sensitivities.breakeven_synergies == b2.sensitivities.breakeven_synergies


def test_projected_balance_sheets_balance_directly(bundle):
    """Independent spot-check of A = L + E on the raw pro forma series, every
    period — the negative-equity target does not break the balance because the
    100% payout holds target equity flat."""
    for combo in bundle.combinations:
        pf = combo.proforma_statements
        for j in range(len(pf.periods)):
            ta = pf.series(LineItem.TOTAL_ASSETS)[j]
            tl = pf.series(LineItem.TOTAL_LIABILITIES)[j]
            te = pf.series(LineItem.TOTAL_EQUITY)[j]
            assert abs(ta - (tl + te)) < 1.0


def test_narrative_has_all_sections():
    """The deal-#2 narrative carries the same nine memo section keys as deal #1."""
    expected = {
        "deal_overview",
        "strategic_rationale",
        "target_valuation",
        "structure_financing",
        "purchase_price_accounting",
        "accretion_dilution",
        "synergies",
        "risks",
        "fairness_comparison",
    }
    assert set(CSCO_SPLK_NARRATIVE.keys()) == expected
    for text in CSCO_SPLK_NARRATIVE.values():
        assert isinstance(text, str) and len(text) > 100
