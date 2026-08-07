"""Offline tests for deal-fact & fairness-opinion extraction from the DEFM14A.

Every extracted figure must carry a DocProvenance with a non-empty accession and
verbatim quote. Covers the deal terms ($197 cash + 0.3450 exchange ratio, implied
$390.19, 29% premium, target shares), Qatalyst's three methodologies with their
disclosed assumption + implied ranges, management projections, and a "tricky"
per-share-vs-aggregate extraction case.
"""

from __future__ import annotations

from src.edgar import extract_deal_terms, extract_fairness_disclosures
from src.edgar.extract import _defm14a
from src.schema import ConsiderationType, DealTerms, FairnessDisclosure


# --- Deal terms ------------------------------------------------------------
def test_extract_deal_terms_core_consideration():
    dt = extract_deal_terms()
    assert isinstance(dt, DealTerms)
    assert dt.acquirer_ticker == "SNPS"
    assert dt.target_ticker == "ANSS"
    assert dt.consideration_type is ConsiderationType.MIXED

    assert dt.cash_per_share is not None
    assert dt.cash_per_share.value == 197.00
    assert dt.exchange_ratio is not None
    assert dt.exchange_ratio.value in (0.345, 0.3450)


def test_deal_terms_every_figure_carries_provenance():
    dt = extract_deal_terms()
    for sv in (
        dt.cash_per_share,
        dt.exchange_ratio,
        dt.stated_price_per_share,
        dt.reference_acquirer_price,
        dt.premium_pct,
        dt.premium_reference_price,
        dt.target_shares_outstanding,
    ):
        assert sv is not None
        assert sv.provenance.accession, f"missing accession on {sv.label}"
        assert sv.provenance.quote, f"missing verbatim quote on {sv.label}"
        assert sv.provenance.form == "DEFM14A"


def test_deal_terms_implied_price_and_premium():
    dt = extract_deal_terms()
    # Headline implied value on the unaffected date.
    assert dt.stated_price_per_share.value == 390.19
    # 29% premium over the $303.16 unaffected ANSS close.
    assert dt.premium_pct.value == 29.0
    assert dt.premium_reference_price.value == 303.16
    # Reference Synopsys price used to value the stock leg.
    assert dt.reference_acquirer_price.value == 559.96


def test_deal_terms_target_shares_outstanding():
    dt = extract_deal_terms()
    assert dt.target_shares_outstanding.value == 87_299_981.0
    assert dt.target_shares_outstanding.unit == "shares"


def test_deal_terms_undisclosed_synergies_are_honest_none():
    # The proxy discusses synergies only qualitatively — no quantified run-rate.
    # Honest-unknown: value is None but provenance records where we looked.
    dt = extract_deal_terms()
    assert dt.disclosed_synergies_annual is not None
    assert dt.disclosed_synergies_annual.value is None
    assert dt.disclosed_synergies_annual.provenance.quote


# --- Fairness disclosures (Qatalyst) --------------------------------------
def test_extract_fairness_has_qatalyst_with_three_methodologies():
    fds = extract_fairness_disclosures()
    assert len(fds) == 1
    fd = fds[0]
    assert isinstance(fd, FairnessDisclosure)
    assert fd.advisor == "Qatalyst Partners"
    assert fd.represents == "ANSS"

    methods = {m.method for m in fd.methodologies}
    assert len(fd.methodologies) >= 3
    assert "Discounted Cash Flow" in methods
    assert "Selected Companies" in methods
    assert "Selected Transactions" in methods


def test_each_methodology_implied_range_carries_provenance():
    fd = extract_fairness_disclosures()[0]
    for m in fd.methodologies:
        assert m.implied_range.low is not None
        assert m.implied_range.high is not None
        assert m.implied_range.low < m.implied_range.high
        assert m.implied_range.provenance.accession
        assert m.implied_range.provenance.quote


def test_dcf_disclosed_assumptions_captured():
    fd = extract_fairness_disclosures()[0]
    dcf = next(m for m in fd.methodologies if m.method == "Discounted Cash Flow")
    # Disclosed WACC/discount-rate range: 10.5%–13.0%.
    dr = dcf.assumptions["discount_rate"]
    assert (dr.low, dr.high) == (10.5, 13.0)
    # Terminal NTM UFCF multiple range: 20.0x–30.0x (Cases 1 & 2).
    mult = dcf.assumptions["ntm_ufcf_multiple"]
    assert (mult.low, mult.high) == (20.0, 30.0)
    # Union implied per-share range across Management Cases 1–3.
    assert dcf.implied_range.low == 160.25
    assert dcf.implied_range.high == 496.04


def test_selected_companies_and_transactions_ranges():
    fd = extract_fairness_disclosures()[0]
    sc = next(m for m in fd.methodologies if m.method == "Selected Companies")
    assert sc.assumptions["cy2024e_lfcf_multiple"].low == 25.0
    assert sc.assumptions["cy2024e_lfcf_multiple"].high == 40.0

    st = next(m for m in fd.methodologies if m.method == "Selected Transactions")
    # Single street-case implied range disclosed as a per-share range.
    assert st.implied_range.low == 199.97
    assert st.implied_range.high == 319.88


def test_management_projections_captured():
    fd = extract_fairness_disclosures()[0]
    assert "revenue" in fd.management_projections
    rev = fd.management_projections["revenue"]
    # FY2024E–FY2033E => 10 projected years.
    assert len(rev) == 10
    assert rev[0].value == 2510.0  # FY2024E revenue ($ millions)
    assert rev[-1].value == 9097.0  # FY2033E revenue
    assert all(s.provenance.quote for s in rev)

    ufcf = fd.management_projections["unlevered_free_cash_flow"]
    assert len(ufcf) == 10
    assert ufcf[0].value == 795.0
    assert ufcf[-1].value == 3178.0


def test_offered_consideration_recorded():
    fd = extract_fairness_disclosures()[0]
    assert fd.offered_consideration is not None
    assert fd.offered_consideration.value == 390.19


# --- Tricky extraction: per-share value vs. the aggregate/large numbers ----
def test_tricky_per_share_not_confused_with_aggregate_figures():
    # The proxy states both a per-share implied value ($390.19) and large
    # aggregate/price figures ($559.96 Synopsys price; 87.3M shares). The
    # extractor must pick the correct per-share consideration ($197 cash, not the
    # $559.96 acquirer price, and not the millions-scale share count).
    dt = extract_deal_terms()
    assert dt.cash_per_share.value == 197.00
    assert dt.cash_per_share.unit == "USD/share"
    # The reference acquirer price is a distinct field, correctly separated.
    assert dt.reference_acquirer_price.value == 559.96
    # Target shares are a shares-scale figure, not dollars, and not the price.
    assert dt.target_shares_outstanding.value == 87_299_981.0
    assert dt.target_shares_outstanding.value != dt.reference_acquirer_price.value


# --- Graceful degradation: no fabrication when figures aren't found --------
def test_extract_deal_terms_from_empty_text_yields_honest_nones():
    # Feeding text with none of the anchors present must not fabricate figures:
    # every optional term degrades to None (the disclosed-synergies field always
    # carries its where-we-looked provenance).
    ref, _ = _defm14a()
    dt = extract_deal_terms(text="no deal figures in this text", ref=ref)
    assert dt.cash_per_share is None
    assert dt.exchange_ratio is None
    assert dt.stated_price_per_share is None
    assert dt.reference_acquirer_price is None
    assert dt.premium_pct is None
    assert dt.target_shares_outstanding is None
    assert dt.disclosed_synergies_annual.value is None
    # Constant identities are still populated from settings.
    assert dt.acquirer_ticker == "SNPS" and dt.target_ticker == "ANSS"


def test_extract_fairness_from_empty_text_yields_no_methodologies():
    ref, _ = _defm14a()
    fds = extract_fairness_disclosures(text="no advisor analyses here", ref=ref)
    assert len(fds) == 1
    fd = fds[0]
    assert fd.advisor == "Qatalyst Partners"
    assert fd.methodologies == []
    assert fd.management_projections == {}
