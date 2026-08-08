"""Verification gates: the XBRL tie-out and the deal-invariant runner.

These are the G1 integration gates. ``tieout`` reconciles historical statement
lines to SEC-reported facts; ``invariants`` re-checks the structural deal
identities (sources = uses, goodwill plug, pro forma balance, EPS bridge,
ownership, synergy phase-in) independently of the engines that produced them.
"""

from __future__ import annotations

from src.verify.audit import AuditReport, audit_workbook
from src.verify.invariants import (
    InvariantReport,
    InvariantResult,
    check_contribution_ties,
    check_eps_bridge_recompute,
    check_goodwill_ties,
    check_pro_forma_balance_sheet,
    check_sources_equal_uses,
    check_synergy_phase_in,
    run_all,
)
from src.verify.report_lint import (
    LintReport,
    collect_engine_numbers,
    extract_report_numbers,
    lint_report_numbers,
)
from src.verify.tieout import (
    TieOutLine,
    TieOutReport,
    balance_sheet_ties,
    tie_out_historical,
)

__all__ = [
    "AuditReport",
    "InvariantReport",
    "InvariantResult",
    "LintReport",
    "TieOutLine",
    "TieOutReport",
    "audit_workbook",
    "balance_sheet_ties",
    "check_contribution_ties",
    "check_eps_bridge_recompute",
    "check_goodwill_ties",
    "check_pro_forma_balance_sheet",
    "check_sources_equal_uses",
    "check_synergy_phase_in",
    "collect_engine_numbers",
    "extract_report_numbers",
    "lint_report_numbers",
    "run_all",
    "tie_out_historical",
]
