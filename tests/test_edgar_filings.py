"""Offline tests for the filing-document retrieval layer.

Covers: submissions-index parsing into FilingRefs with the correct Archives URL,
form/date filtering, offline text retrieval of a cached document, and HTML->text
stripping (stdlib only, no new dependency).
"""

from __future__ import annotations

from datetime import date

import pytest
from src.edgar import (
    archives_url,
    find_documents,
    get_document_text,
    html_to_text,
    list_filings,
)
from src.edgar.filings import FilingRef

_DEFM14A_ACCESSION = "0001140361-24-020334"


# --- URL construction ------------------------------------------------------
def test_archives_url_unpads_cik_and_strips_accession_dashes():
    url = archives_url("0001013462", _DEFM14A_ACCESSION, "ny20025601x1_defm14a.htm")
    assert url == (
        "https://www.sec.gov/Archives/edgar/data/1013462/"
        "000114036124020334/ny20025601x1_defm14a.htm"
    )


def test_filing_ref_url_property():
    ref = FilingRef(
        ticker="ANSS",
        cik="0001013462",
        form="DEFM14A",
        filed=date(2024, 4, 17),
        accession=_DEFM14A_ACCESSION,
        primary_document="ny20025601x1_defm14a.htm",
    )
    assert ref.accession_nodash == "000114036124020334"
    assert ref.url.endswith("000114036124020334/ny20025601x1_defm14a.htm")


# --- Submissions-index parsing --------------------------------------------
def test_list_filings_parses_defm14a_ref():
    refs = list_filings("ANSS", forms={"DEFM14A"})
    assert len(refs) == 1
    ref = refs[0]
    assert ref.form == "DEFM14A"
    assert ref.accession == _DEFM14A_ACCESSION
    assert ref.filed == date(2024, 4, 17)
    assert ref.url == (
        "https://www.sec.gov/Archives/edgar/data/1013462/"
        "000114036124020334/ny20025601x1_defm14a.htm"
    )


def test_list_filings_form_normalization_matches_variants():
    # "S-4" filter should match "S-4" (and "S-4/A" via space/slash-insensitive norm).
    refs = list_filings("SNPS", forms={"S-4"})
    forms = {r.form for r in refs}
    assert any(f.replace("/", "").replace(" ", "") == "S-4" for f in forms)


def test_list_filings_date_filter_and_sort_newest_first():
    refs = list_filings("ANSS", since=date(2024, 1, 1), until=date(2024, 12, 31))
    assert refs, "expected 2024 filings"
    assert all(date(2024, 1, 1) <= r.filed <= date(2024, 12, 31) for r in refs)
    # Sorted newest-first.
    assert refs == sorted(refs, key=lambda r: r.filed, reverse=True)


# --- Offline document text retrieval --------------------------------------
def test_get_document_text_reads_cached_defm14a():
    ref = list_filings("ANSS", forms={"DEFM14A"})[0]
    text = get_document_text(ref, offline=True)
    assert len(text) > 100_000  # the proxy is a large document
    assert "Qatalyst Partners" in text
    assert "0.3450" in text  # the exchange ratio survives the strip


def test_get_document_text_offline_missing_raises():
    ref = FilingRef(
        ticker="ANSS",
        cik="0001013462",
        form="8-K",
        filed=date(2099, 1, 1),
        accession="9999999999-99-999999",
        primary_document="nope.htm",
    )
    with pytest.raises(FileNotFoundError):
        get_document_text(ref, offline=True)


def test_find_documents_pairs_refs_with_text():
    docs = find_documents("SNPS", forms={"S-4"})
    assert len(docs) >= 1
    ref, text = docs[0]
    assert ref.form.replace("/", "").replace(" ", "").startswith("S-4")
    assert "Synopsys" in text or "Ansys" in text


# --- HTML -> text ----------------------------------------------------------
def test_html_to_text_strips_tags_and_unescapes_entities():
    html = "<html><head><style>a{color:red}</style></head><body>Hi&nbsp;<b>there</b>!</body></html>"
    assert html_to_text(html) == "Hi there!"


def test_html_to_text_drops_script_content():
    html = "<div>keep<script>var x = 1; document.write('drop me')</script>after</div>"
    out = html_to_text(html)
    assert "keep" in out and "after" in out
    assert "drop me" not in out
