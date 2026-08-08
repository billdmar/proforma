"""Precedent-transactions loader: parse the curated premiums-paid CSV.

Reads a curated CSV of comparable M&A deals (each row sourced) into the frozen
``PrecedentTransaction`` contract (src/interfaces.py) and computes summary
statistics across the set for the memo's precedents / premiums-paid table.

Design notes:

* **Known columns, tolerant of extras.** The loader reads the columns it needs
  (``date,acquirer,target,ev,ev_revenue,ev_ebitda,source``) by name via
  ``csv.DictReader``. Any additional column the curator adds — e.g.
  ``premium_pct`` — is simply ignored during parsing; it does not break the
  loader. Only the required columns must be present.

* **Honest unknowns.** A blank ``ev_revenue`` or ``ev_ebitda`` cell parses to
  None (the deal disclosed no such multiple), never 0 — a fabricated 0 would
  drag the medians down and read as a real data point. ``ev`` is required
  (a precedent with no enterprise value cannot anchor a multiple), so a blank
  ``ev`` raises cleanly rather than being silently coerced.

* **Summary stats skip None.** ``summary_stats`` computes median/mean/min/max
  per multiple over only the present values, mirroring the honest-unknown rule
  in the comps engine.

This module is self-contained (no imports from sibling engines): it reuses the
parsing/stats *approach* of the thesis comps engine, cited in docs/DESIGN.md,
without importing it.
"""

from __future__ import annotations

import csv
from statistics import mean, median

from src.interfaces import PrecedentTransaction

# Columns the loader requires to build a PrecedentTransaction. Any other column
# in the CSV (e.g. premium_pct) is read opportunistically or ignored.
_REQUIRED_COLUMNS = ("date", "acquirer", "target", "ev", "ev_revenue", "ev_ebitda", "source")

# Metrics summary_stats reports on, in order. ev_revenue/ev_ebitda are always
# candidates; premium_pct is included only if the rows carry it ("if present"),
# so the loader stays useful for a CSV that adds a premium column later.
_STAT_METRICS = ("ev_revenue", "ev_ebitda", "premium_pct")


def _parse_optional_float(raw: str | None) -> float | None:
    """A blank cell is an honest unknown (None); otherwise parse the float."""
    if raw is None or raw.strip() == "":
        return None
    return float(raw)


def load_precedents(csv_path: str) -> list[PrecedentTransaction]:
    """Parse the curated precedent-transactions CSV into typed records.

    Header must contain ``date,acquirer,target,ev,ev_revenue,ev_ebitda,source``;
    extra columns are ignored. ``ev`` is required per row; blank ``ev_revenue``
    and ``ev_ebitda`` cells parse to None. Raises FileNotFoundError for a
    missing file and ValueError for a missing required column or unparseable
    numeric cell.
    """
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in _REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"precedents CSV {csv_path} missing required columns: {missing}")

        out: list[PrecedentTransaction] = []
        for row in reader:
            out.append(
                PrecedentTransaction(
                    date=row["date"].strip(),
                    acquirer=row["acquirer"].strip(),
                    target=row["target"].strip(),
                    ev=float(row["ev"]),
                    ev_revenue=_parse_optional_float(row.get("ev_revenue")),
                    ev_ebitda=_parse_optional_float(row.get("ev_ebitda")),
                    source=row["source"].strip(),
                )
            )
    return out


def _stats(values: list[float]) -> dict[str, float]:
    """median/mean/min/max over a non-empty list of present (non-None) values."""
    return {
        "median": median(values),
        "mean": mean(values),
        "min": min(values),
        "max": max(values),
    }


def summary_stats(precedents: list[PrecedentTransaction]) -> dict[str, dict[str, float]]:
    """median/mean/min/max per multiple across the precedent set, skipping None.

    Reports ``ev_revenue`` and ``ev_ebitda`` (and ``premium_pct`` when the
    records carry it). A metric with no present values across the set is
    omitted entirely rather than reported as an empty/zero block.
    """
    out: dict[str, dict[str, float]] = {}
    for metric in _STAT_METRICS:
        present = [v for p in precedents if (v := getattr(p, metric, None)) is not None]
        if present:
            out[metric] = _stats(present)
    return out
