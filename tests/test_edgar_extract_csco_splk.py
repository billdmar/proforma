"""Offline tests for deal #2 (Cisco/Splunk) extraction from the Splunk DEFM14A.

The P6 generality proof: a SECOND real deal through the same contracts. Cisco
acquired Splunk for $157.00 per share in cash (all-cash), so the exchange ratio
is honestly None. Splunk had TWO financial advisors — Qatalyst Partners and
Morgan Stanley — so ``extract_fairness_disclosures_csco_splk`` returns two
disclosures, each scoped to its own opinion section.

Every extracted figure must carry a DocProvenance with the right accession
(0001140361-23-050211) and a non-empty verbatim quote. The "tricky" test
verifies the two advisors' DCF ranges are attributed to the correct advisor
(distinct discount rates + distinct implied ranges), guarding against
cross-attribution between the two co-located opinion sections.
"""

from __future__ import annotations

from src.edgar import (
    extract_deal_terms_csco_splk,
    extract_fairness_disclosures_csco_splk,
)
from src.edgar.extract_csco_splk import _defm14a
from src.schema import ConsiderationType, DealTerms, FairnessDisclosure

_ACCESSION = "0001140361-23-050211"


# --- Deal terms ------------------------------------------------------------
def test_extract_deal_terms_core_consideration():
    dt = extract_deal_terms_csco_splk()
    assert isinstance(dt, DealTerms)
    assert dt.acquirer_ticker == "CSCO"
    assert dt.target_ticker == "SPLK"
    # All-cash deal.
    assert dt.consideration_type is ConsiderationType.CASH
    assert dt.cash_per_share is not None
    assert dt.cash_per_share.value == 157.00
    assert dt.cash_per_share.unit == "USD/share"
    # No stock leg: exchange ratio and reference acquirer price are honest None.
    assert dt.exchange_ratio is None
    assert dt.reference_acquirer_price is None


def test_deal_terms_target_shares_outstanding():
    dt = extract_deal_terms_csco_splk()
    assert dt.target_shares_outstanding is not None
    assert dt.target_shares_outstanding.value == 168_536_732.0
    assert dt.target_shares_outstanding.unit == "shares"


def test_deal_terms_premium_present_and_referenced():
    dt = extract_deal_terms_csco_splk()
    assert dt.premium_pct is not None
    assert dt.premium_pct.value == 31.0
    # Premium is measured over the $119.59 unaffected close (Sept 20, 2023).
    assert dt.premium_reference_price is not None
    assert dt.premium_reference_price.value == 119.59


def test_deal_terms_dates():
    dt = extract_deal_terms_csco_splk()
    assert dt.announce_date.isoformat() == "2023-09-21"
    # Close confirmed from Splunk's completion 8-K (accession 0001104659-24-035289).
    assert dt.close_date is not None
    assert dt.close_date.isoformat() == "2024-03-18"


def test_deal_terms_every_populated_figure_carries_provenance():
    dt = extract_deal_terms_csco_splk()
    for sv in (
        dt.cash_per_share,
        dt.stated_price_per_share,
        dt.premium_pct,
        dt.premium_reference_price,
        dt.target_shares_outstanding,
    ):
        assert sv is not None
        assert sv.provenance.accession == _ACCESSION, f"wrong accession on {sv.label}"
        assert sv.provenance.quote, f"missing verbatim quote on {sv.label}"
        assert sv.provenance.form == "DEFM14A"


def test_deal_terms_undisclosed_synergies_are_honest_none():
    dt = extract_deal_terms_csco_splk()
    assert dt.disclosed_synergies_annual is not None
    assert dt.disclosed_synergies_annual.value is None
    assert dt.disclosed_synergies_annual.provenance.quote


# --- Fairness disclosures (two advisors) -----------------------------------
def test_two_disclosures_both_advise_splunk():
    fds = extract_fairness_disclosures_csco_splk()
    assert len(fds) == 2
    assert all(isinstance(fd, FairnessDisclosure) for fd in fds)
    assert {fd.advisor for fd in fds} == {"Qatalyst Partners", "Morgan Stanley"}
    assert all(fd.represents == "SPLK" for fd in fds)


def test_each_disclosure_has_dcf_and_multiple_methodologies():
    fds = extract_fairness_disclosures_csco_splk()
    for fd in fds:
        methods = {m.method for m in fd.methodologies}
        assert len(fd.methodologies) >= 1
        assert "Discounted Cash Flow" in methods


def test_every_dcf_implied_range_valid_and_sourced():
    fds = extract_fairness_disclosures_csco_splk()
    for fd in fds:
        dcf = next(m for m in fd.methodologies if m.method == "Discounted Cash Flow")
        assert dcf.implied_range.low is not None
        assert dcf.implied_range.high is not None
        assert dcf.implied_range.low < dcf.implied_range.high
        assert dcf.implied_range.provenance.accession == _ACCESSION
        assert dcf.implied_range.provenance.quote


def test_dcf_ranges_are_distinct_objects_scoped_correctly():
    # The two advisors' opinion sections are co-located in the proxy; a scoping
    # bug would return the same range object (or identical values) for both.
    fds = extract_fairness_disclosures_csco_splk()
    qat = next(fd for fd in fds if fd.advisor == "Qatalyst Partners")
    ms = next(fd for fd in fds if fd.advisor == "Morgan Stanley")
    qat_dcf = next(m for m in qat.methodologies if m.method == "Discounted Cash Flow")
    ms_dcf = next(m for m in ms.methodologies if m.method == "Discounted Cash Flow")
    assert qat_dcf.implied_range is not ms_dcf.implied_range
    assert (qat_dcf.implied_range.low, qat_dcf.implied_range.high) != (
        ms_dcf.implied_range.low,
        ms_dcf.implied_range.high,
    )


def test_tricky_dcf_attributed_to_correct_advisor():
    # Attribution guard. The two advisors disclose DIFFERENT DCF assumptions and
    # implied ranges; scoping must map each to the right advisor:
    #   Qatalyst: discount rate 12.0%-14.0%; union implied 100.95-196.81.
    #   Morgan Stanley: discount rate 11.6%-13.5%; union implied 100.00-212.00.
    fds = extract_fairness_disclosures_csco_splk()
    qat = next(fd for fd in fds if fd.advisor == "Qatalyst Partners")
    ms = next(fd for fd in fds if fd.advisor == "Morgan Stanley")

    qat_dcf = next(m for m in qat.methodologies if m.method == "Discounted Cash Flow")
    ms_dcf = next(m for m in ms.methodologies if m.method == "Discounted Cash Flow")

    assert (
        qat_dcf.assumptions["discount_rate"].low,
        qat_dcf.assumptions["discount_rate"].high,
    ) == (12.0, 14.0)
    assert (ms_dcf.assumptions["discount_rate"].low, ms_dcf.assumptions["discount_rate"].high) == (
        11.6,
        13.5,
    )

    assert (qat_dcf.implied_range.low, qat_dcf.implied_range.high) == (100.95, 196.81)
    assert (ms_dcf.implied_range.low, ms_dcf.implied_range.high) == (100.0, 212.0)


def test_tricky_seltxn_ranges_belong_to_qatalyst_not_dcf():
    # Ground-truth correction: $97.37-$178.26 and $88.22-$172.96 are BOTH
    # Qatalyst's Selected Transactions sub-analyses (NTM revenue and NTM EBITDA),
    # NOT DCF ranges and NOT split across the two advisors. Verify they land on
    # Qatalyst's Selected Transactions methodology and NOT on any DCF range.
    fds = extract_fairness_disclosures_csco_splk()
    qat = next(fd for fd in fds if fd.advisor == "Qatalyst Partners")
    seltxn = next(m for m in qat.methodologies if m.method == "Selected Transactions")
    # Union across NTM revenue (97.37-178.26), NTM EBITDA (88.22-172.96) and
    # NTM LFCF (107.27-171.63) sub-analyses.
    assert seltxn.implied_range.low == 88.22
    assert seltxn.implied_range.high == 178.26

    for fd in fds:
        dcf = next(m for m in fd.methodologies if m.method == "Discounted Cash Flow")
        assert dcf.implied_range.low not in (97.37, 88.22)
        assert dcf.implied_range.high not in (178.26, 172.96)


def test_qatalyst_selected_companies_multiple_captured():
    fds = extract_fairness_disclosures_csco_splk()
    qat = next(fd for fd in fds if fd.advisor == "Qatalyst Partners")
    sc = next(m for m in qat.methodologies if m.method == "Selected Companies")
    mult = sc.assumptions["cy2024e_revenue_multiple"]
    assert (mult.low, mult.high) == (4.0, 7.0)
    assert mult.provenance.accession == _ACCESSION


def test_morgan_stanley_has_public_trading_and_precedent():
    fds = extract_fairness_disclosures_csco_splk()
    ms = next(fd for fd in fds if fd.advisor == "Morgan Stanley")
    methods = {m.method for m in ms.methodologies}
    assert "Public Trading Comparables" in methods
    assert "Precedent Transactions" in methods
    for m in ms.methodologies:
        assert m.implied_range.low is not None
        assert m.implied_range.high is not None
        assert m.implied_range.low < m.implied_range.high


def test_management_projections_captured_for_both_advisors():
    # Both advisors relied on the same Management Projections; the Baseline
    # revenue and UFCF rows span FY2024E-FY2034E (11 years).
    fds = extract_fairness_disclosures_csco_splk()
    for fd in fds:
        rev = fd.management_projections["revenue"]
        assert len(rev) == 11
        assert rev[0].value == 4038.0  # FY2024E revenue ($ millions)
        assert rev[-1].value == 13462.0  # FY2034E revenue
        assert all(s.provenance.quote for s in rev)

        ufcf = fd.management_projections["unlevered_free_cash_flow"]
        assert len(ufcf) == 11
        assert ufcf[0].value == 937.0
        assert ufcf[-1].value == 5483.0


def test_offered_consideration_is_all_cash_price():
    fds = extract_fairness_disclosures_csco_splk()
    for fd in fds:
        assert fd.offered_consideration is not None
        assert fd.offered_consideration.value == 157.00


# --- Graceful degradation: no fabrication when figures aren't found --------
def test_extract_deal_terms_from_empty_text_yields_honest_nones():
    ref, _ = _defm14a()
    dt = extract_deal_terms_csco_splk(text="no deal figures in this text", ref=ref)
    assert dt.cash_per_share is None
    assert dt.stated_price_per_share is None
    assert dt.premium_pct is None
    assert dt.premium_reference_price is None
    assert dt.target_shares_outstanding is None
    assert dt.exchange_ratio is None
    assert dt.reference_acquirer_price is None
    assert dt.disclosed_synergies_annual.value is None
    # Constant identities are still populated.
    assert dt.acquirer_ticker == "CSCO" and dt.target_ticker == "SPLK"
    assert dt.consideration_type is ConsiderationType.CASH


def test_extract_fairness_from_empty_text_yields_two_empty_disclosures():
    ref, _ = _defm14a()
    fds = extract_fairness_disclosures_csco_splk(text="no advisor analyses here", ref=ref)
    assert len(fds) == 2
    assert {fd.advisor for fd in fds} == {"Qatalyst Partners", "Morgan Stanley"}
    for fd in fds:
        assert fd.methodologies == []
        assert fd.management_projections == {}
