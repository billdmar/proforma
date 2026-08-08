"""The EDGAR layer: SEC client, XBRL normalization, filing retrieval, deal extraction.

The single-company client + normalization halves are ported from the thesis
project (cited in docs/DESIGN.md); the filing-document retrieval and deal/
fairness extraction halves are net-new for proforma's merger model.
"""

from __future__ import annotations

from src.edgar.client import EdgarClient
from src.edgar.extract import extract_deal_terms, extract_fairness_disclosures
from src.edgar.extract_csco_splk import (
    extract_deal_terms_csco_splk,
    extract_fairness_disclosures_csco_splk,
)
from src.edgar.filings import (
    FilingRef,
    archives_url,
    find_documents,
    get_document_text,
    html_to_text,
    list_filings,
)
from src.edgar.normalize import ALIAS_MAP, load_normalized_facts

__all__ = [
    "ALIAS_MAP",
    "EdgarClient",
    "FilingRef",
    "archives_url",
    "extract_deal_terms",
    "extract_deal_terms_csco_splk",
    "extract_fairness_disclosures",
    "extract_fairness_disclosures_csco_splk",
    "find_documents",
    "get_document_text",
    "html_to_text",
    "list_filings",
    "load_normalized_facts",
]
