"""Tests for the M&A committee memo renderer (src/report/render.py + template.py).

Builds the real flagship Synopsys/ANSYS bundle once at module scope, renders the
memo to a temp PDF with the authored narrative, and asserts: the PDF is written
and non-trivial; no ``[DRAFT:`` placeholders remain; the nine MEMO_SPEC section
headings and the disclaimer are present; known engine figures appear in table
exhibits; and every number in every ``<table>`` traces to an engine display-form
(the G3 report-lint gate). Offline (no live EDGAR); charts render headless (Agg).
"""

from __future__ import annotations

import os
import tempfile

import pytest
from src.flagship import build_flagship_bundle
from src.narrative import SNPS_ANSS_NARRATIVE
from src.report.render import render_memo
from src.report.template import build_html
from src.verify.report_lint import (
    collect_engine_numbers,
    extract_report_numbers,
    lint_report_numbers,
)

_PRECEDENTS_CSV = "data/curated/precedents_software.csv"

_SECTION_HEADINGS = [
    "Deal Overview",
    "Strategic Rationale",
    "Target Valuation",
    "Structure &amp; Financing",
    "Purchase Price Accounting",
    "Accretion / Dilution",
    "Synergies",
    "Risks",
    "Fairness-Opinion Comparison",
]


@pytest.fixture(scope="module")
def bundle():
    return build_flagship_bundle(_PRECEDENTS_CSV)


@pytest.fixture(scope="module")
def rendered(bundle, tmp_path_factory):
    """Render the memo once for the module; returns (html, pdf_path)."""
    d = tmp_path_factory.mktemp("memo")
    assets = str(d / "assets")
    html = build_html(bundle, assets, SNPS_ANSS_NARRATIVE)
    pdf = str(d / "SNPS_ANSS_deal_memo.pdf")
    render_memo(bundle, pdf, assets, SNPS_ANSS_NARRATIVE)
    return html, pdf


# --- PDF output -----------------------------------------------------------
def test_pdf_written_and_non_trivial(rendered):
    _, pdf = rendered
    assert os.path.exists(pdf)
    # A real multi-page memo with inlined chart PNGs is well over 20 KB.
    assert os.path.getsize(pdf) > 20_000


def test_render_returns_out_path(bundle):
    with tempfile.TemporaryDirectory() as d:
        assets = os.path.join(d, "assets")
        out = os.path.join(d, "memo.pdf")
        result = render_memo(bundle, out, assets, SNPS_ANSS_NARRATIVE)
        assert result == out
        assert os.path.exists(out)


# --- HTML structure -------------------------------------------------------
def test_all_nine_section_headings_present(rendered):
    html, _ = rendered
    for heading in _SECTION_HEADINGS:
        assert heading in html, heading


def test_disclaimer_present(rendered):
    html, _ = rendered
    assert "Educational reconstruction from public SEC filings" in html
    assert "no verdict on" in html


def test_no_draft_placeholders_when_narrative_supplied(rendered):
    html, _ = rendered
    assert "[DRAFT:" not in html


def test_tables_present(rendered):
    html, _ = rendered
    assert html.count("<table") >= 8  # one exhibit per major section


def test_known_engine_figure_appears_in_table(bundle, rendered):
    html, _ = rendered
    # Goodwill ~$22,603 mm renders in the PPA walk table.
    goodwill_mm = f"{bundle.deal.ppa.goodwill / 1e6:,.0f}"
    tables = " ".join(
        __import__("re").findall(r"<table.*?</table>", html, flags=16)  # re.DOTALL
    )
    assert goodwill_mm in tables
    # Total per-share consideration appears somewhere in a table.
    tps = f"{bundle.deal.consideration.total_per_share:,.2f}"
    assert tps in tables


# --- The G3 report-lint gate ---------------------------------------------
def test_every_table_number_traces_to_engine(bundle, rendered):
    html, _ = rendered
    rendered_nums = extract_report_numbers(html, tables_only=True)
    engine = collect_engine_numbers(bundle)
    report = lint_report_numbers(rendered_nums, engine)
    assert report.passed, sorted(report.unsourced)
    assert report.numbers_checked > 30


def test_placeholder_used_when_narrative_missing(bundle):
    with tempfile.TemporaryDirectory() as d:
        html = build_html(bundle, os.path.join(d, "a"), narrative=None)
    assert "[DRAFT: deal_overview]" in html
