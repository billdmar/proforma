"""Standalone dual-company 3-statement models (acquirer + target).

Company-agnostic: the same ``ThreeStatementBuilder`` models both SNPS and ANSS
off ``NormalizedFacts``. See ``builder.py``.
"""

from __future__ import annotations

from src.standalone.builder import ThreeStatementBuilder, balance_check

__all__ = ["ThreeStatementBuilder", "balance_check"]
