#!/usr/bin/env python
"""Build every Synopsys/ANSYS deliverable from cached data, in one command.

    python scripts/build_deliverables.py

Deterministic: the model is built once via :func:`build_flagship_bundle` and
every artifact is derived from that single bundle, so a rebuild reproduces
identical numbers (the determinism requirement). No number is hand-typed here —
the script only orchestrates the writers.

Outputs
    out/SNPS_ANSS_merger_model.xlsx    live-formula workbook (scratch)
    out/SNPS_ANSS_deal_memo.pdf        M&A committee memo (scratch)
    out/assets/*.png                   rendered charts (scratch)
    releases/SNPS_ANSS_merger_model.xlsx   committed deliverable
    releases/SNPS_ANSS_deal_memo.pdf       committed deliverable
    docs/img/accretion_by_year.png     hero chart (README)
    docs/img/target_football.png       hero chart (README)

macOS: WeasyPrint's native libs live under the Homebrew prefix — set here before
any import triggers the native load. Inert on CI/Linux.
"""

from __future__ import annotations

# Must precede any import that transitively loads WeasyPrint's native deps.
import os

os.environ.setdefault("DYLD_FALLBACK_LIBRARY_PATH", "/opt/homebrew/lib")

import shutil  # noqa: E402
import sys  # noqa: E402
from pathlib import Path  # noqa: E402

# Make ``src``/``config`` importable no matter the invocation directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.flagship import AS_OF, build_flagship_bundle  # noqa: E402
from src.flagship_csco_splk import (  # noqa: E402
    build_flagship_bundle as build_csco_splk_bundle,
)
from src.narrative import SNPS_ANSS_NARRATIVE  # noqa: E402
from src.narrative_csco_splk import CSCO_SPLK_NARRATIVE  # noqa: E402
from src.report import render_memo  # noqa: E402
from src.workbook import ExcelWorkbookWriter, cache_formula_values  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
ASSETS = OUT / "assets"
RELEASES = ROOT / "releases"
DOCS = ROOT / "docs"
DOCS_IMG = DOCS / "img"
PRECEDENTS_CSV = ROOT / "data" / "curated" / "precedents_software.csv"

# One entry per deal. Deal #1 (Synopsys/ANSYS) supplies the README hero charts;
# deal #2 (Cisco/Splunk) is the P6 generality proof through the same engine.
DEALS = {
    "snps_anss": {
        "build": build_flagship_bundle,
        "narrative": SNPS_ANSS_NARRATIVE,
        "xlsx": "SNPS_ANSS_merger_model.xlsx",
        "pdf": "SNPS_ANSS_deal_memo.pdf",
        "hero_charts": ("accretion_by_year.png", "target_football.png"),
        "label": "Synopsys/ANSYS",
    },
    "csco_splk": {
        "build": build_csco_splk_bundle,
        "narrative": CSCO_SPLK_NARRATIVE,
        "xlsx": "CSCO_SPLK_merger_model.xlsx",
        "pdf": "CSCO_SPLK_deal_memo.pdf",
        "hero_charts": (),  # deal #1 supplies the README heroes
        "label": "Cisco/Splunk",
    },
}


def _manifest_line(path: Path) -> str:
    kb = path.stat().st_size / 1024
    return f"  {path.relative_to(ROOT)}  ({kb:,.1f} KB)"


def _build_deal(deal_key: str) -> list[Path]:
    """Build one deal's workbook + memo deterministically and publish to releases/."""
    cfg = DEALS[deal_key]
    assets = ASSETS / deal_key  # per-deal chart dir so the two memos don't collide
    assets.mkdir(parents=True, exist_ok=True)

    # Single source of truth: build the bundle once, derive everything from it.
    model = cfg["build"](precedents_csv=str(PRECEDENTS_CSV))
    written: list[Path] = []

    # 1. Live-formula workbook + cached values (so no-recalc previewers show
    #    numbers while formulas stay live for Excel).
    xlsx_out = OUT / cfg["xlsx"]
    ExcelWorkbookWriter().write(str(xlsx_out), model)
    cache_formula_values(str(xlsx_out))
    written.append(xlsx_out)

    # 2. M&A committee memo PDF (charts rendered into out/assets/<deal>, inlined).
    pdf_out = OUT / cfg["pdf"]
    render_memo(model, str(pdf_out), str(assets), narrative=cfg["narrative"], as_of=AS_OF)
    written.append(pdf_out)

    # 3. Publish committed deliverables into releases/.
    for name in (cfg["xlsx"], cfg["pdf"]):
        dst = RELEASES / name
        shutil.copyfile(OUT / name, dst)
        written.append(dst)

    # 4. Copy any hero charts into docs/img for the README.
    for chart in cfg["hero_charts"]:
        dst = DOCS_IMG / chart
        shutil.copyfile(assets / chart, dst)
        written.append(dst)

    return written


def main(deal_keys: list[str] | None = None) -> None:
    for d in (OUT, ASSETS, RELEASES, DOCS, DOCS_IMG):
        d.mkdir(parents=True, exist_ok=True)
    for deal_key in deal_keys or list(DEALS):
        written = _build_deal(deal_key)
        print(f"Built {DEALS[deal_key]['label']} deliverables (deterministic):")
        for p in written:
            print(_manifest_line(p))


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Build proforma deliverables (workbook + memo).")
    ap.add_argument(
        "--deal",
        choices=[*sorted(DEALS), "all"],
        default="all",
        help="which deal to build (default: all)",
    )
    args = ap.parse_args()
    main(None if args.deal == "all" else [args.deal])
