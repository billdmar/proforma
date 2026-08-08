"""Tests for the report-number provenance lint (src/verify/report_lint.py).

Unit-tests the three functions: ``collect_engine_numbers`` on the flagship
merger bundle (known goodwill / EPS figures present in some display form),
``extract_report_numbers`` on small HTML tables (scoping + malformed-token
tolerance), and ``lint_report_numbers`` both clean and with an injected
fabricated number (flagged). Mirrors the thesis project's test style. Offline
(no live EDGAR).
"""

from __future__ import annotations

from src.flagship import build_flagship_bundle
from src.interfaces import (
    FairnessDifferentialReport,
    MethodologyReproduction,
    SensitivityGrid,
    SensitivitySet,
)
from src.verify.report_lint import (
    LintReport,
    collect_engine_numbers,
    extract_report_numbers,
    lint_report_numbers,
)

_PRECEDENTS_CSV = "data/curated/precedents_software.csv"


# --- collect_engine_numbers ------------------------------------------------


def test_collect_engine_numbers_contains_known_figures():
    bundle = build_flagship_bundle(_PRECEDENTS_CSV)
    engine = collect_engine_numbers(bundle)
    assert len(engine) > 50

    # Goodwill (~$22.6B) must be present in its billions display form.
    goodwill = bundle.deal.ppa.goodwill
    assert round(goodwill / 1e9, 1) in engine

    # Year-1 pro forma EPS (~$7.91) present at its raw per-share magnitude.
    eps_y1 = bundle.primary_combination().eps_bridge[0].pro_forma_eps
    assert round(eps_y1, 2) in engine

    # Equity purchase price present in millions form.
    epp = bundle.deal.consideration.equity_purchase_price
    assert round(epp / 1e6, 0) in engine


def test_collect_engine_numbers_feeds_a_clean_lint():
    bundle = build_flagship_bundle(_PRECEDENTS_CSV)
    engine = collect_engine_numbers(bundle)
    # A report citing the goodwill (in $B) and Y1 EPS lints clean.
    rendered = {
        round(bundle.deal.ppa.goodwill / 1e9, 1),
        round(bundle.primary_combination().eps_bridge[0].pro_forma_eps, 2),
    }
    report = lint_report_numbers(rendered, engine)
    assert report.passed, sorted(report.unsourced)


def test_collect_engine_numbers_covers_precedents():
    # With precedents loaded, their EV/multiple magnitudes appear as display forms.
    bundle = build_flagship_bundle(_PRECEDENTS_CSV)
    engine = collect_engine_numbers(bundle)
    pt = bundle.precedents[0]
    if pt.ev_ebitda is not None:
        assert round(pt.ev_ebitda, 1) in engine


def test_collect_engine_numbers_covers_sensitivities_and_fairness():
    # The flagship bundle carries neither sensitivities nor a fairness
    # differential yet (populated at G2); attach small ones so those branches
    # are walked and their figures surface as engine display-forms.
    bundle = build_flagship_bundle(_PRECEDENTS_CSV)
    grid = SensitivityGrid(
        year_idx=0,
        row_label="premium",
        col_label="synergies",
        row_values=[0.20, 0.30],
        col_values=[100_000_000.0, 200_000_000.0],
        values=[[0.011, 0.022], [0.033, None]],
    )
    bundle.sensitivities = SensitivitySet(
        premium_x_synergies=grid,
        consideration_mix=grid,
        breakeven_synergies=175_000_000.0,
    )
    bundle.fairness_differential = FairnessDifferentialReport(
        reproductions=[
            MethodologyReproduction(
                advisor="Evercore",
                method="DCF",
                disclosed_low=280.0,
                disclosed_high=360.0,
                our_low=285.0,
                our_high=355.0,
                overlap_pct=0.88,
            )
        ]
    )
    engine = collect_engine_numbers(bundle)
    assert 175.0 in engine  # breakeven synergies in $M
    assert 285.0 in engine  # our_low disclosed range
    assert round(0.033 * 100.0, 1) in engine  # a grid cell rendered as percent


def test_collect_engine_numbers_narrative_allowlist_expands():
    # The NARRATIVE_SOURCED_FACTS allowlist mechanism feeds display-forms too.
    import src.verify.report_lint as rl

    bundle = build_flagship_bundle(_PRECEDENTS_CSV)
    original = rl.NARRATIVE_SOURCED_FACTS
    try:
        rl.NARRATIVE_SOURCED_FACTS = {123.45}
        engine = collect_engine_numbers(bundle)
        assert 123.45 in engine
    finally:
        rl.NARRATIVE_SOURCED_FACTS = original


# --- extract_report_numbers ------------------------------------------------


def test_extractor_scopes_to_tables_and_ignores_dates_fy_labels():
    html = (
        "<p>Prose 999.99 not in scope.</p>"
        "<table><tr><td>Revenue FY27E on 2024-12-17</td><td>5.5</td>"
        "<td>128.00</td></tr></table>"
    )
    nums = extract_report_numbers(html)
    assert 5.5 in nums and 128.0 in nums
    assert 999.99 not in nums  # prose is out of scope (tables_only)
    assert 2024 not in nums and 27 not in nums and 17 not in nums


def test_extractor_tolerates_malformed_numeric_tokens():
    # Bare/stray tokens (a lone dash, a trailing-dot fragment) and $-signs must
    # not crash the extractor or parse into spurious floats — it skips what it
    # can't cleanly read and still pulls the real figure.
    html = "<table><tr><td>-</td><td>$</td><td>.</td><td>4,321.00</td></tr></table>"
    nums = extract_report_numbers(html)
    assert 4321.0 in nums
    assert all(n == 4321.0 for n in nums)


def test_extractor_can_scan_full_html_when_not_tables_only():
    html = "<p>Prose figure 777.77 here.</p><table><tr><td>5.5</td></tr></table>"
    nums = extract_report_numbers(html, tables_only=False)
    assert 777.77 in nums and 5.5 in nums


def test_extractor_drops_bare_years_and_small_integers():
    # Plain (non-ISO, non-FY) integer tokens that are years or small counts are
    # dropped as labels; genuine financial figures survive.
    html = "<table><tr><td>2025</td><td>15</td><td>150.0</td></tr></table>"
    nums = extract_report_numbers(html)
    assert nums == {150.0}


def test_extractor_drops_zero_and_strips_base64_charts():
    html = (
        '<table><tr><td><img src="data:image/png;base64,AAAABBBB1234=="></td>'
        "<td>0</td><td>0.00</td><td>612.34</td></tr></table>"
    )
    nums = extract_report_numbers(html)
    assert nums == {612.34}  # zeros dropped; base64 chart digits stripped


# --- lint_report_numbers ---------------------------------------------------


def test_lint_passes_when_all_numbers_sourced():
    engine = {100.0, 250.5, 42.0}
    rendered = {100.0, 42.0}
    report = lint_report_numbers(rendered, engine)
    assert report.passed
    assert report.numbers_checked == 2


def test_lint_flags_fabricated_number():
    engine = {100.0, 250.5}
    rendered = {100.0, 8675.31}  # fabricated token has no engine source
    report = lint_report_numbers(rendered, engine)
    assert not report.passed
    assert 8675.31 in report.unsourced


def test_lint_catches_fabricated_number_against_real_engine_set():
    bundle = build_flagship_bundle(_PRECEDENTS_CSV)
    engine = collect_engine_numbers(bundle)
    rendered = {
        round(bundle.deal.ppa.goodwill / 1e9, 1),
        8675.31,  # fabricated
    }
    report = lint_report_numbers(rendered, engine)
    assert not report.passed
    assert any(abs(x - 8675.31) < 0.01 for x in report.unsourced)


def test_lint_tolerance_allows_near_matches():
    engine = {100.0}
    rendered = {100.005}  # within default abs_tol
    assert lint_report_numbers(rendered, engine).passed
    assert not lint_report_numbers(rendered, engine, abs_tol=1e-6).passed


def test_lint_report_summaries_reflect_pass_and_fail():
    assert "PASS" in LintReport(numbers_checked=2).summary()
    assert "UNSOURCED" in LintReport(numbers_checked=2, unsourced=[9.0]).summary()
