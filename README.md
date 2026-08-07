# proforma

**A merger model built on a real announced deal — reconstructed from SEC
filings, expressed as a live-formula Excel model and an M&A committee memo, and
differentially verified against the deal's own disclosed fairness opinions.**

Deal under reconstruction: **Synopsys, Inc. (SNPS) → ANSYS, Inc. (ANSS)**,
announced January 2024, a ~$35B cash-and-stock transaction.

> _Educational reconstruction from public SEC filings. Not investment advice.
> Synergy figures are labeled assumptions, not forecasts. No verdict is passed
> on whether the transaction should occur; no endorsement by the SEC, the named
> companies, or their financial advisors is implied._

---

## What it produces
- **A live-formula Excel merger model** — dual-company standalone models
  (XBRL-tied historicals + driver-based projections), deal structure & sources
  and uses, purchase price accounting → goodwill, pro forma income statement and
  balance sheet, accretion/dilution by year, contribution & exchange-ratio
  analysis, sensitivity grids, precedents, and a fairness-opinion comparison tab.
- **An M&A committee memo PDF** — deal overview, strategic rationale, target
  valuation, structure & financing, the accretion/dilution story, synergies
  (management's disclosed figure vs. our conservative case), risks, and the
  fairness-opinion comparison appendix.
- **The Python engine** that computes every number and verifies both deliverables.

## Verification — the moat
Every number is engine-computed and machine-checked:
- **Dual-company XBRL tie-out** — both companies' historical statement lines
  reconcile to SEC-reported facts.
- **Excel ↔ Python cell differential** — the workbook is recalculated and every
  computed cell matches the engine to the cent.
- **Deal invariants** — sources = uses; goodwill ties to the purchase-price
  walk; the pro forma balance sheet balances every period; the EPS bridge and
  accretion/dilution recompute independently; contribution ties to ownership.
- **Fairness differential** — the advisors' disclosed assumption ranges, run
  through our engine, reproduce their disclosed implied valuation ranges.
- **Determinism** — a full rebuild from cached data reproduces identical numbers.

_Headline figures, verification counts, and deliverable links are filled in at
G4 once the model is built and verified._

## Quickstart
```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
PROFORMA_OFFLINE=1 .venv/bin/python -m pytest -m "not live" --cov=src
```
See `docs/ENV.md` for the toolchain (macOS WeasyPrint note) and `docs/DESIGN.md`
for the architecture. SEC data is used under the EDGAR fair-access policy;
committed fixtures are public-domain filings.

## License
MIT — see `LICENSE`.
