"""Offline tests for the precedent-transactions loader (src/precedents).

Covers: parsing a curated CSV into PrecedentTransaction records with a blank
numeric cell honoured as None, hand-verified summary statistics (incl. the
extra premium_pct column), source-citation round-trip, tolerance of unknown
columns, and clean errors for a missing file / missing required column.
"""

from __future__ import annotations

import pytest
from src.interfaces import PrecedentTransaction
from src.precedents import load_precedents, summary_stats

# Header carries an EXTRA premium_pct column (not part of PrecedentTransaction)
# plus an entirely unrelated column to prove unknown columns are tolerated. One
# ev_ebitda cell is intentionally blank (honest unknown -> None).
_CSV = """date,acquirer,target,ev,ev_revenue,ev_ebitda,premium_pct,source,analyst_note
2022-05-26,Broadcom,VMware,61000000000,8.0,20.0,0.30,"Broadcom 8-K (Acc 0001-22)",ignored
2022-09-15,Adobe,Figma,20000000000,6.0,,0.20,"Adobe 8-K (Acc 0002-22)",ignored
2016-06-13,Microsoft,LinkedIn,26200000000,10.0,15.0,0.40,"MSFT DEFM14A (Acc 0003-16)",ignored
2019-06-10,Salesforce,Tableau,15700000000,4.0,25.0,0.10,"CRM S-4 (Acc 0004-19)",ignored
"""


def _write_csv(tmp_path, text: str) -> str:
    path = tmp_path / "precedents.csv"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_parses_records_and_blank_cell_is_none(tmp_path):
    precedents = load_precedents(_write_csv(tmp_path, _CSV))

    assert len(precedents) == 4
    assert all(isinstance(p, PrecedentTransaction) for p in precedents)

    figma = next(p for p in precedents if p.target == "Figma")
    assert figma.acquirer == "Adobe"
    assert figma.ev == 20000000000.0
    assert figma.ev_revenue == 6.0
    assert figma.ev_ebitda is None  # blank cell -> honest unknown, never 0


def test_source_citation_round_trips(tmp_path):
    precedents = load_precedents(_write_csv(tmp_path, _CSV))
    vmware = next(p for p in precedents if p.target == "VMware")
    assert vmware.source == "Broadcom 8-K (Acc 0001-22)"


def test_summary_stats_are_hand_correct(tmp_path):
    stats = summary_stats(load_precedents(_write_csv(tmp_path, _CSV)))

    # ev_revenue present values sorted: [4.0, 6.0, 8.0, 10.0]
    assert stats["ev_revenue"]["median"] == 7.0  # (6+8)/2
    assert stats["ev_revenue"]["mean"] == 7.0  # 28/4
    assert stats["ev_revenue"]["min"] == 4.0
    assert stats["ev_revenue"]["max"] == 10.0

    # ev_ebitda present values (Figma blank skipped): [15.0, 20.0, 25.0]
    assert stats["ev_ebitda"]["median"] == 20.0
    assert stats["ev_ebitda"]["mean"] == 20.0
    assert stats["ev_ebitda"]["min"] == 15.0
    assert stats["ev_ebitda"]["max"] == 25.0

    # premium_pct is EXTRA (not on PrecedentTransaction) -> not summarised.
    assert "premium_pct" not in stats


def test_missing_optional_metric_is_omitted_from_stats(tmp_path):
    # Every ev_ebitda blank -> the metric has no present values and is omitted
    # entirely rather than reported as an empty/zero block.
    csv_text = (
        "date,acquirer,target,ev,ev_revenue,ev_ebitda,source\n"
        "2022-05-26,A,B,100,5.0,,S1\n"
        "2022-06-26,C,D,200,7.0,,S2\n"
    )
    stats = summary_stats(load_precedents(_write_csv(tmp_path, csv_text)))
    assert "ev_ebitda" not in stats
    assert stats["ev_revenue"]["median"] == 6.0


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_precedents(str(tmp_path / "does_not_exist.csv"))


def test_missing_required_column_raises(tmp_path):
    # No `ev` column -> cannot anchor a multiple; fail loudly, not silently.
    bad = "date,acquirer,target,ev_revenue,ev_ebitda,source\n2022-01-01,A,B,5.0,10.0,S\n"
    with pytest.raises(ValueError, match="missing required columns"):
        load_precedents(_write_csv(tmp_path, bad))
