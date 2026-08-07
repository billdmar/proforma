# ENV.md — build environment & toolchain

## Dev machine (this build)
- **Hardware:** Apple Silicon Mac (arm64).
- **OS:** macOS 26.5 (Darwin 25.5.0, build 25F71).
- **Python:** 3.12.13 in a project-local venv at `.venv/` (system `python3` is 3.14 — **must** use the 3.12 venv).
- **Package manager:** pip (venv). Deps pinned in `pyproject.toml` for determinism.

## CI machine
- `ubuntu-latest` (GitHub Actions), Python 3.12.
- `PROFORMA_OFFLINE=1` — CI **never** touches live EDGAR; runs on committed fixtures only.
- Coverage gate: `--cov-fail-under=90`.

## Pinned dependencies (see `pyproject.toml`)
| Package | Version | Role |
|---|---|---|
| requests | 2.34.2 | live EDGAR fetch (offline path never imports it) |
| numpy | 2.5.1 | numerics |
| pandas | 3.0.5 | tabular helpers |
| openpyxl | 3.1.5 | live-formula .xlsx writer |
| matplotlib | 3.11.1 | memo charts (Agg backend) |
| formulas | 1.3.4 | Excel recalc for the cell-level differential |
| weasyprint | 69.0 | memo PDF render |
| python-dateutil | 2.9.0.post0 | period parsing |
| pytest / pytest-cov / coverage / ruff | 9.1.1 / 7.1.0 / 7.15.3 / 0.16.1 | test + lint |

## macOS native-library note (WeasyPrint)
WeasyPrint needs Pango/Cairo/GDK-Pixbuf/libffi shared libs. They are installed via Homebrew
(`brew install pango cairo gdk-pixbuf libffi`) under `/opt/homebrew/lib`. On macOS the renderer
sets `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` **before** importing weasyprint (inert on
Linux/CI, where apt installs the libs on the default loader path). Verified working: weasyprint 69.0.

## Setup from scratch
```bash
~/.local/bin/python3.12 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
# macOS only, if not already present:
brew install pango cairo gdk-pixbuf libffi
```

## SEC fair-access
Every EDGAR request carries `User-Agent: proforma-research billdmar@gmail.com`, spaced ≥150ms
(≤10 req/s), and every response is cached under `data/fixtures/`. Fixtures are committed
(SEC filings are public domain); CI runs on them alone.
