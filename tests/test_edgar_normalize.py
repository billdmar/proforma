"""Offline tests for XBRL normalization against the committed SNPS/ANSS fixtures.

Covers: the alias map's shape, that BOTH deal companies load real multi-year
revenue, tag-drift/priority selection on synthetic facts, and a restatement
resolution (latest accession wins; superseded trail retained).
"""

from __future__ import annotations

from datetime import date

import pytest
from config import settings
from src.edgar import ALIAS_MAP, load_normalized_facts
from src.edgar.normalize import _normalize_line_item
from src.schema import (
    CompanyMeta,
    LineItem,
    NormalizedFacts,
    Period,
    PeriodType,
)


# --- Alias map shape -------------------------------------------------------
def test_alias_map_covers_all_line_items():
    missing = [li.name for li in LineItem if li not in ALIAS_MAP or not ALIAS_MAP[li]]
    assert not missing, f"LineItems with no alias candidates: {missing}"


def test_alias_map_entries_are_taxonomy_tag_pairs():
    for li, tags in ALIAS_MAP.items():
        for entry in tags:
            assert isinstance(entry, tuple) and len(entry) == 2, f"{li}: bad entry {entry}"
            tax, tag = entry
            assert tax in {"us-gaap", "dei", "srt"}, f"{li}: unexpected taxonomy {tax}"
            assert isinstance(tag, str) and tag


# --- Both deal companies load ---------------------------------------------
def test_load_snps_company_meta():
    nf = load_normalized_facts("SNPS")
    assert nf.company.cik == settings.ACQUIRER_CIK == "0000883241"
    assert nf.company.ticker == "SNPS"
    assert "SYNOPSYS" in nf.company.name.upper()


def test_load_anss_company_meta():
    nf = load_normalized_facts("ANSS")
    assert nf.company.cik == settings.TARGET_CIK == "0001013462"
    assert nf.company.ticker == "ANSS"
    assert "ANSYS" in nf.company.name.upper()


def test_snps_annual_revenue_multiple_periods():
    nf = load_normalized_facts("SNPS")
    rev = [
        (p.fy, nf.value(LineItem.REVENUE, p))
        for p in nf.annual_periods()
        if nf.value(LineItem.REVENUE, p) is not None
    ]
    assert len(rev) >= 5
    by_year = dict(rev)
    # Recent fiscal years tie out to the reported SEC facts (raw USD magnitudes).
    assert by_year[2024] == 6_127_436_000.0
    assert by_year[2025] == 7_054_178_000.0


def test_anss_annual_revenue_multiple_periods():
    nf = load_normalized_facts("ANSS")
    rev = [
        (p.fy, nf.value(LineItem.REVENUE, p))
        for p in nf.annual_periods()
        if nf.value(LineItem.REVENUE, p) is not None
    ]
    assert len(rev) >= 5
    by_year = dict(rev)
    # ANSYS tags revenue as us-gaap:Revenues (not the newer contract-revenue tag).
    assert by_year[2023] == 2_269_949_000.0
    assert by_year[2024] == 2_544_809_000.0
    latest = nf.annual_periods()[-1]
    assert nf.get(LineItem.REVENUE, latest).provenance.xbrl_tag == "Revenues"


def test_both_companies_balance_sheet_instants_present():
    # The latest instant may be a cover-page dei shares-outstanding date (no
    # balance-sheet lines), so assert against instants that DO carry total assets.
    for ticker in ("SNPS", "ANSS"):
        nf = load_normalized_facts(ticker)
        ta = [
            nf.value(LineItem.TOTAL_ASSETS, p)
            for p in nf.instant_periods()
            if nf.value(LineItem.TOTAL_ASSETS, p) is not None
        ]
        assert len(ta) >= 5
        cash = [
            nf.value(LineItem.CASH, p)
            for p in nf.instant_periods()
            if nf.value(LineItem.CASH, p) is not None
        ]
        assert len(cash) >= 5


def test_provenance_carries_tag_and_accession():
    nf = load_normalized_facts("SNPS")
    latest = nf.annual_periods()[-1]
    fact = nf.get(LineItem.REVENUE, latest)
    assert fact is not None
    assert fact.provenance.taxonomy == "us-gaap"
    assert fact.provenance.accession  # non-empty
    assert fact.provenance.form.startswith("10-K")


def test_honest_unknown_for_unreported_concept():
    # A concept the filer never reports must be absent (None), never fabricated.
    nf = load_normalized_facts("SNPS")
    fake = Period(PeriodType.INSTANT, end=date(1990, 1, 1))
    assert nf.value(LineItem.TOTAL_ASSETS, fake) is None


# --- Restatement resolution: latest accession wins, superseded retained ----
def test_real_restatement_latest_accession_wins():
    # SNPS revenue for at least one FY was restated across accessions; the
    # normalizer keeps the latest-filed value and retains the superseded trail.
    nf = load_normalized_facts("SNPS")
    restated = [f for f in nf.facts.values() if f.line_item is LineItem.REVENUE and f.superseded]
    assert restated, "expected at least one revenue restatement in the SNPS fixture"
    for f in restated:
        # Winner is the latest-filed; every superseded provenance is older.
        assert all(s.filed <= f.provenance.filed for s in f.superseded)


def _fake_facts(points_by_tag: dict[str, list[dict]]) -> dict:
    return {"us-gaap": {tag: {"units": {"USD": pts}} for tag, pts in points_by_tag.items()}}


def test_within_tag_restatement_latest_accession_wins():
    # Same tag, same period, two filings: the later-filed accession wins and the
    # superseded earlier filing is retained (the NormalizedFacts.add contract).
    period = {"start": "2018-04-01", "end": "2019-03-31", "fp": "FY", "form": "10-K", "fy": 2019}
    old = {**period, "val": 1000.0, "accn": "acc-2019", "filed": "2019-05-30"}
    restated = {**period, "val": 1010.0, "accn": "acc-2020", "filed": "2020-05-30"}
    facts = _fake_facts({"CostOfGoodsAndServicesSold": [old, restated]})
    nf = NormalizedFacts(company=CompanyMeta(cik="1", ticker="X", name="X"))
    _normalize_line_item(nf, facts, LineItem.COST_OF_REVENUE, ALIAS_MAP[LineItem.COST_OF_REVENUE])

    p = Period(PeriodType.DURATION, end=date(2019, 3, 31), start=date(2018, 4, 1), fy=2019, fp="FY")
    got = nf.get(LineItem.COST_OF_REVENUE, p)
    assert got is not None
    assert got.value == 1010.0
    assert got.provenance.accession == "acc-2020"
    assert any(s.accession == "acc-2019" for s in got.superseded)


def test_priority_does_not_conflate_disagreeing_tags():
    # Two tags map to OTHER_CURRENT_ASSETS but report different values for the
    # same period. Priority selection takes the higher-priority tag only.
    period_a = {"end": "2025-03-31", "fp": "FY", "form": "10-K", "fy": 2025}
    high = {**period_a, "val": 67_282_000.0, "accn": "a", "filed": "2025-05-01"}
    low = {**period_a, "val": 39_294_000.0, "accn": "b", "filed": "2025-05-01"}
    facts = _fake_facts({"OtherAssetsCurrent": [high], "PrepaidExpenseCurrent": [low]})
    nf = NormalizedFacts(company=CompanyMeta(cik="1", ticker="X", name="X"))
    _normalize_line_item(
        nf, facts, LineItem.OTHER_CURRENT_ASSETS, ALIAS_MAP[LineItem.OTHER_CURRENT_ASSETS]
    )
    p = Period(PeriodType.INSTANT, end=date(2025, 3, 31))
    got = nf.get(LineItem.OTHER_CURRENT_ASSETS, p)
    assert got is not None
    assert got.value == 67_282_000.0
    assert got.provenance.xbrl_tag == "OtherAssetsCurrent"


def test_missing_companyfacts_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_normalized_facts("ZZZZ", facts_dir=tmp_path)
