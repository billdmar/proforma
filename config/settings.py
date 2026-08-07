"""Project-wide configuration constants. ORCH-owned.

Adapted from the thesis project's config/settings.py (cited in docs/DESIGN.md) —
same SEC fair-access scaffolding, retargeted to the proforma merger deal.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- Paths ---
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
FIXTURES_DIR = DATA_DIR / "fixtures"
CURATED_DIR = DATA_DIR / "curated"
OUT_DIR = ROOT / "out"
RELEASES_DIR = ROOT / "releases"

# --- SEC EDGAR fair-access (CLAUDE.md: this is law here) ---
# Contact confirmed by the owner at W0.
SEC_USER_AGENT = "proforma-research billdmar@gmail.com"
SEC_MAX_REQ_PER_SEC = 10
SEC_REQ_SPACING_SEC = 0.15  # 150ms spacing
SEC_BASE_URL = "https://data.sec.gov"
SEC_WWW_URL = "https://www.sec.gov"

# CI and offline runs must never hit live EDGAR — fixtures only.
OFFLINE = os.environ.get("PROFORMA_OFFLINE") == "1"

# --- The deal (chosen at W0; terms provenance-verified during extraction) ---
ACQUIRER_TICKER = "SNPS"
ACQUIRER_CIK = "0000883241"  # Synopsys, Inc. — verified against EDGAR at fixture-pull
ACQUIRER_NAME = "Synopsys, Inc."

TARGET_TICKER = "ANSS"
TARGET_CIK = "0001013462"  # ANSYS, Inc. — verified against EDGAR at fixture-pull
TARGET_NAME = "ANSYS, Inc."

DEAL_SLUG = "SNPS_ANSS"
