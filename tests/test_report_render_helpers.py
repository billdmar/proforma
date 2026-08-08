"""Unit tests for the memo template's pure helpers and guard branches.

These cover the formatting helpers' honest-unknown (``None`` -> em-dash) paths,
the display-scale branches, the deterministic date formatter's fallback, and the
empty-data guards in the exhibit builders — the branches the full-render test
doesn't exercise because the flagship bundle is always fully populated.
"""

from __future__ import annotations

import dataclasses

from src.flagship import build_flagship_bundle
from src.report import template as tpl
from src.schema import LineItem, Period, PeriodType

_PRECEDENTS_CSV = "data/curated/precedents_software.csv"


def _stmt_with_revenue(peak: float | None):
    from datetime import date

    p = Period(ptype=PeriodType.DURATION, end=date(2024, 12, 31), start=date(2024, 1, 1), fp="FY")
    from src.interfaces import StatementSet

    return StatementSet(periods=[p], rows={LineItem.REVENUE: [peak]}, n_hist=1)


# --- formatting helpers: honest-unknown paths ------------------------------
def test_formatters_none_returns_em_dash():
    assert tpl._usd(None) == "—"
    assert tpl._usd2(None) == "—"
    assert tpl._num(None) == "—"
    assert tpl._pct(None) == "—"
    assert tpl._mult(None) == "—"
    assert tpl._shares(None) == "—"
    assert tpl._net_cash_phrase(None, 1e9, "bn") == "—"
    assert tpl._ratio(None, 1.0) is None
    assert tpl._ratio(1.0, 0) is None


def test_formatters_render_values():
    assert tpl._usd(1_000, 1e3, " k") == "$1 k"
    assert tpl._usd2(390.19) == "$390.19"
    assert tpl._num(2_500_000, 1e6, dp=1) == "2.5"
    assert tpl._pct(0.287) == "28.7%"
    assert tpl._mult(20.6) == "20.6x"
    assert tpl._shares(87_299_981) == "87.3M"
    assert tpl._ratio(2.0, 4.0) == 0.5


def test_net_cash_phrase_sign_sense():
    assert tpl._net_cash_phrase(-743_309_000, 1e9, "bn").startswith("net cash")
    assert tpl._net_cash_phrase(1_000_000_000, 1e9, "bn").startswith("net debt")


def test_auto_scale_branches():
    assert tpl._auto_scale(_stmt_with_revenue(5e9)) == (1e9, "bn")
    assert tpl._auto_scale(_stmt_with_revenue(5e6)) == (1e6, "mm")
    assert tpl._auto_scale(_stmt_with_revenue(500.0)) == (1.0, "")
    assert tpl._auto_scale(_stmt_with_revenue(None)) == (1.0, "")


def test_report_date_fallback_on_bad_input():
    assert tpl._report_date("2026-08-08") == "August 08, 2026"
    assert tpl._report_date("not-a-date") == "not-a-date"


# --- guard branches on the exhibit builders --------------------------------
def test_exhibit_guards_when_data_absent(tmp_path):
    bundle = build_flagship_bundle(_PRECEDENTS_CSV, with_sensitivities=False, with_fairness=False)
    empty = dataclasses.replace(bundle, precedents=[], target_dcf=None)
    assert "No precedent transactions loaded" in tpl._precedents_table(empty)
    assert "No sensitivity grid available" in tpl._sensitivity_grid_table(empty)
    assert "No fairness differential available" in tpl._fairness_table(empty)
    # Target-valuation section renders its DCF-absent row rather than crashing.
    from src.report.charts import build_all_charts

    charts = build_all_charts(empty, str(tmp_path))
    assert "Standalone DCF not available" in tpl._target_valuation(empty, charts, None)
