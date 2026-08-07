"""Tests for the XBRL tie-out gate (``src.verify.tieout``).

Two layers:

* **Unit** — hand-built ``NormalizedFacts`` + ``StatementSet`` exercise every
  branch of the reconciler: an income line that matches its fact, a balance line
  resolved via its period-end instant, a value that disagrees with its fact, a
  derived subtotal (gross profit) that reconciles to its components, a derived
  subtotal missing a component, and a value with no fact that is not a
  recognized subtotal. ``balance_sheet_ties`` is checked with and without a
  tagged total-liabilities line.

* **Dual-company real tie-out (G1 gate)** — load the committed SNPS and ANSS
  fixtures, build each historical ``StatementSet``, and assert every historical
  line reconciles to the SEC-reported fact to the dollar for BOTH companies.
"""

from __future__ import annotations

from datetime import date

from src.edgar import load_normalized_facts
from src.schema import (
    CompanyMeta,
    Fact,
    LineItem,
    NormalizedFacts,
    Period,
    PeriodType,
    Provenance,
    Unit,
)
from src.standalone import ThreeStatementBuilder
from src.verify.tieout import balance_sheet_ties, tie_out_historical

# --------------------------------------------------------------------------- #
# unit-test scaffolding (we own these inputs)
# --------------------------------------------------------------------------- #
_PROV = Provenance(
    xbrl_tag="Revenues",
    taxonomy="us-gaap",
    unit=Unit.USD,
    accession="0000000000-24-000001",
    form="10-K",
    filed=date(2024, 2, 1),
)


def _dur(y: int) -> Period:
    return Period(PeriodType.DURATION, end=date(y, 12, 31), start=date(y, 1, 1), fy=y, fp="FY")


def _inst(y: int) -> Period:
    return Period(PeriodType.INSTANT, end=date(y, 12, 31), fy=y, fp="FY")


def _fact(li: LineItem, period: Period, value: float) -> Fact:
    return Fact(line_item=li, period=period, value=value, provenance=_PROV)


class _StmtStub:
    """Minimal StatementSet-shaped stub for the reconciler (periods/rows/n_hist
    + a .series() and .rows dict — all the reconciler touches)."""

    def __init__(self, periods, rows, n_hist):
        self.periods = periods
        self.rows = rows
        self.n_hist = n_hist

    def series(self, li):
        return self.rows.get(li, [None] * len(self.periods))


# --------------------------------------------------------------------------- #
# unit tests — reconciler branches
# --------------------------------------------------------------------------- #
def test_income_and_balance_lines_reconcile_to_facts():
    """An income line resolves to its DURATION fact; a balance line resolves to
    the matching period-end INSTANT fact; both tie out to the dollar."""
    dur, inst = _dur(2024), _inst(2024)
    facts = NormalizedFacts(company=CompanyMeta(cik="1", ticker="X", name="X"))
    facts.add(_fact(LineItem.REVENUE, dur, 6000.0))
    facts.add(_fact(LineItem.TOTAL_ASSETS, inst, 20000.0))

    stmts = _StmtStub(
        periods=[dur],
        rows={LineItem.REVENUE: [6000.0], LineItem.TOTAL_ASSETS: [20000.0]},
        n_hist=1,
    )
    report = tie_out_historical(stmts, facts, tol=0.0)
    assert report.passed
    assert report.checked == 2
    assert "2/2" in report.summary()


def test_value_disagreeing_with_fact_is_a_mismatch():
    dur = _dur(2024)
    facts = NormalizedFacts(company=CompanyMeta(cik="1", ticker="X", name="X"))
    facts.add(_fact(LineItem.REVENUE, dur, 6000.0))
    stmts = _StmtStub(periods=[dur], rows={LineItem.REVENUE: [6001.0]}, n_hist=1)

    report = tie_out_historical(stmts, facts, tol=0.0)
    assert not report.passed
    assert len(report.mismatches) == 1
    assert report.mismatches[0].note == "value != SEC fact"
    assert "MISMATCH" in report.summary()


def test_derived_gross_profit_reconciles_to_components():
    """Gross profit has no tagged fact but reconciles to revenue − cost."""
    dur = _dur(2024)
    facts = NormalizedFacts(company=CompanyMeta(cik="1", ticker="X", name="X"))
    facts.add(_fact(LineItem.REVENUE, dur, 6000.0))
    facts.add(_fact(LineItem.COST_OF_REVENUE, dur, 2000.0))
    stmts = _StmtStub(
        periods=[dur],
        rows={
            LineItem.REVENUE: [6000.0],
            LineItem.COST_OF_REVENUE: [2000.0],
            LineItem.GROSS_PROFIT: [4000.0],  # derived, no fact
        },
        n_hist=1,
    )
    report = tie_out_historical(stmts, facts, tol=0.0)
    assert report.passed
    gp = next(line for line in report.lines if line.line_item is LineItem.GROSS_PROFIT)
    assert gp.fact_value is None and gp.ok


def test_derived_missing_component_flags():
    dur = _dur(2024)
    facts = NormalizedFacts(company=CompanyMeta(cik="1", ticker="X", name="X"))
    stmts = _StmtStub(
        periods=[dur],
        rows={LineItem.GROSS_PROFIT: [4000.0]},  # no revenue/cost present
        n_hist=1,
    )
    report = tie_out_historical(stmts, facts, tol=0.0)
    assert not report.passed
    assert "missing component" in report.mismatches[0].note


def test_value_without_fact_and_not_derived_flags():
    dur = _dur(2024)
    facts = NormalizedFacts(company=CompanyMeta(cik="1", ticker="X", name="X"))
    stmts = _StmtStub(periods=[dur], rows={LineItem.NET_INCOME: [1200.0]}, n_hist=1)
    report = tie_out_historical(stmts, facts, tol=0.0)
    assert not report.passed
    assert report.mismatches[0].note == "no SEC fact and not a recognized derived subtotal"


def test_none_values_are_skipped():
    dur = _dur(2024)
    facts = NormalizedFacts(company=CompanyMeta(cik="1", ticker="X", name="X"))
    stmts = _StmtStub(periods=[dur], rows={LineItem.NET_INCOME: [None]}, n_hist=1)
    report = tie_out_historical(stmts, facts, tol=0.0)
    assert report.checked == 0
    assert report.passed


# --------------------------------------------------------------------------- #
# unit tests — balance_sheet_ties
# --------------------------------------------------------------------------- #
def test_balance_sheet_ties_with_tagged_total_liabilities():
    facts = NormalizedFacts(company=CompanyMeta(cik="1", ticker="X", name="X"))
    inst = _inst(2024)
    facts.add(_fact(LineItem.TOTAL_ASSETS, inst, 20000.0))
    facts.add(_fact(LineItem.TOTAL_LIABILITIES, inst, 8000.0))
    facts.add(_fact(LineItem.TOTAL_EQUITY, inst, 12000.0))
    residuals = balance_sheet_ties(facts)
    assert residuals == [(2024, 0.0)]


def test_balance_sheet_ties_infers_missing_liabilities():
    facts = NormalizedFacts(company=CompanyMeta(cik="1", ticker="X", name="X"))
    inst = _inst(2024)
    facts.add(_fact(LineItem.TOTAL_ASSETS, inst, 20000.0))
    facts.add(_fact(LineItem.TOTAL_EQUITY, inst, 12000.0))
    # No total-liabilities fact → inferred; residual 0 by construction.
    residuals = balance_sheet_ties(facts)
    assert residuals == [(2024, 0.0)]


def test_balance_sheet_ties_skips_periods_missing_assets_or_equity():
    facts = NormalizedFacts(company=CompanyMeta(cik="1", ticker="X", name="X"))
    inst = _inst(2024)
    facts.add(_fact(LineItem.TOTAL_ASSETS, inst, 20000.0))  # no equity → skipped
    assert balance_sheet_ties(facts) == []


# --------------------------------------------------------------------------- #
# DUAL-COMPANY REAL TIE-OUT — the G1 gate (offline, committed fixtures)
# --------------------------------------------------------------------------- #
def test_dual_company_real_tieout_snps_and_anss():
    """Both deal companies' historical statement lines reconcile to the
    SEC-reported facts to the dollar (tol=0.0) — the dual-company XBRL tie-out
    the G1 gate requires. Prints the per-company reconciled line counts."""
    builder = ThreeStatementBuilder()
    counts: dict[str, int] = {}
    for ticker in ("SNPS", "ANSS"):
        facts = load_normalized_facts(ticker)
        hist = builder.build_historical(facts)
        report = tie_out_historical(hist, facts, tol=0.0)
        assert report.checked > 100, f"{ticker}: expected many historical lines"
        assert report.passed, f"{ticker} tie-out mismatches:\n" + "\n".join(
            f"  {m.line_item.value} FY{m.fy}: stmt={m.statement_value} "
            f"fact={m.fact_value} ({m.note})"
            for m in report.mismatches[:25]
        )
        counts[ticker] = report.checked
    # Surfaced in -s output; also a floor assertion so the gate stays meaningful.
    print(f"\nDual-company tie-out line counts: {counts}")
    assert counts["SNPS"] > 100 and counts["ANSS"] > 100


def test_balance_sheet_identity_from_raw_facts_both_companies():
    """Independent BS identity straight from raw facts.

    ANSS ties to the dollar every period. SNPS carries a small residual in some
    years because it tags equity as ``StockholdersEquityIncludingPortion-
    AttributableToNoncontrollingInterest`` (so TotalAssets = TotalLiabilities +
    equity-incl-NCI) while ``TOTAL_EQUITY`` normalizes to the parent-only
    ``StockholdersEquity`` — the residual is the noncontrolling-interest wedge, a
    genuine parent-vs-consolidated disclosure feature, not a builder error. We
    bound it as a small fraction of total assets rather than tune it away (the
    dollar-exact gate is the *built-statement* tie-out above)."""
    from src.schema import LineItem

    # ANSS: no NCI wedge → ties to the dollar.
    anss = load_normalized_facts("ANSS")
    anss_resid = balance_sheet_ties(anss)
    assert anss_resid, "ANSS: expected instant periods with BS data"
    assert all(abs(r) <= 1.0 for _, r in anss_resid), "ANSS: BS identity off"

    # SNPS: bound the NCI/parent-equity wedge to a small % of total assets.
    snps = load_normalized_facts("SNPS")
    snps_resid = balance_sheet_ties(snps)
    assert snps_resid, "SNPS: expected instant periods with BS data"
    ta_by_end = {p.end.year: snps.value(LineItem.TOTAL_ASSETS, p) for p in snps.instant_periods()}
    for year, resid in snps_resid:
        ta = ta_by_end.get(year)
        if ta:
            assert abs(resid) / ta < 0.015, f"SNPS FY{year}: BS wedge {resid} > 1.5% of assets"
