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
from src.narrative import SNPS_ANSS_NARRATIVE  # noqa: E402
from src.report import render_memo  # noqa: E402
from src.workbook import ExcelWorkbookWriter  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
ASSETS = OUT / "assets"
RELEASES = ROOT / "releases"
DOCS = ROOT / "docs"
DOCS_IMG = DOCS / "img"
PRECEDENTS_CSV = ROOT / "data" / "curated" / "precedents_software.csv"

XLSX_NAME = "SNPS_ANSS_merger_model.xlsx"
PDF_NAME = "SNPS_ANSS_deal_memo.pdf"
# Hero charts surfaced on the README (rendered into out/assets by the memo
# pipeline; copied to docs/img so they render on GitHub without a build).
HERO_CHARTS = ("accretion_by_year.png", "target_football.png")


def _manifest_line(path: Path) -> str:
    kb = path.stat().st_size / 1024
    return f"  {path.relative_to(ROOT)}  ({kb:,.1f} KB)"


def main() -> None:
    for d in (OUT, ASSETS, RELEASES, DOCS, DOCS_IMG):
        d.mkdir(parents=True, exist_ok=True)

    # Single source of truth: build the bundle once, derive everything from it.
    model = build_flagship_bundle(precedents_csv=str(PRECEDENTS_CSV))

    written: list[Path] = []

    # 1. Live-formula workbook.
    xlsx_out = OUT / XLSX_NAME
    ExcelWorkbookWriter().write(str(xlsx_out), model)
    written.append(xlsx_out)

    # 2. M&A committee memo PDF (charts rendered into out/assets, inlined).
    pdf_out = OUT / PDF_NAME
    render_memo(model, str(pdf_out), str(ASSETS), narrative=SNPS_ANSS_NARRATIVE, as_of=AS_OF)
    written.append(pdf_out)

    # 3. Publish committed deliverables into releases/.
    for name in (XLSX_NAME, PDF_NAME):
        dst = RELEASES / name
        shutil.copyfile(OUT / name, dst)
        written.append(dst)

    # 4. Copy the hero charts into docs/img for the README.
    for chart in HERO_CHARTS:
        dst = DOCS_IMG / chart
        shutil.copyfile(ASSETS / chart, dst)
        written.append(dst)

    print("Built Synopsys/ANSYS deliverables (deterministic):")
    for p in written:
        print(_manifest_line(p))


if __name__ == "__main__":
    main()
