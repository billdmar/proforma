"""Filing-document retrieval: submissions index -> Archives URLs -> document text.

NET-NEW for proforma (the thesis project had no document layer — it worked only
from the structured CompanyFacts API). This module bridges from the submissions
JSON to the actual filing *documents* (DEFM14A / S-4 / 8-K / 425) whose text the
extraction layer reads:

* :func:`list_filings` parses ``submissions.filings.recent`` into typed
  :class:`FilingRef` descriptors (form / filed / accession / primary document),
  with optional form and date filtering.
* :func:`archives_url` builds the canonical
  ``https://www.sec.gov/Archives/edgar/data/{cik}/{accn_nodash}/{doc}`` URL.
* :func:`get_document_text` returns the plain text of a filing, offline-first:
  it locates the cached HTML under ``data/fixtures/documents/`` by accession
  number (the committed fixtures are named
  ``{TICKER}_{FORM}_{ACCESSION}_{DOC}.htm``) and strips it to text. In OFFLINE
  mode a cache miss is a loud error, never a live fetch.
* :func:`find_documents` is the one-call helper: ticker + form/date filters ->
  list of ``(FilingRef, text)``.

HTML->text uses only the stdlib (``html.parser`` + ``html.unescape``); no new
dependency is introduced (hard rule: no deps beyond the pinned set).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

from config import settings

from src.edgar.client import EdgarClient

# Committed deal documents live here (offline-first source of truth).
DOCUMENTS_DIR = settings.FIXTURES_DIR / "documents"

# Tags whose textual content is not body copy and must be dropped wholesale.
_SKIP_TAGS = {"script", "style", "head"}


@dataclass(frozen=True)
class FilingRef:
    """One filing from the submissions index, with a resolvable document URL."""

    ticker: str
    cik: str  # zero-padded 10-digit
    form: str  # "DEFM14A", "S-4", "8-K", "425", ...
    filed: date
    accession: str  # dashed accession, e.g. "0001140361-24-020334"
    primary_document: str  # primary document filename within the filing

    @property
    def accession_nodash(self) -> str:
        return self.accession.replace("-", "")

    @property
    def url(self) -> str:
        return archives_url(self.cik, self.accession, self.primary_document)


def archives_url(cik: str, accession: str, document: str) -> str:
    """Canonical SEC Archives URL for a filing document.

    ``cik`` may be zero-padded; EDGAR's Archives path uses the un-padded integer.
    ``accession`` is the dashed form; the path uses it with dashes removed.
    """
    cik_int = int(cik)
    accn_nodash = accession.replace("-", "")
    return f"{settings.SEC_WWW_URL}/Archives/edgar/data/{cik_int}/{accn_nodash}/{document}"


class _TextExtractor(HTMLParser):
    """Collect body text, dropping script/style/head content."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self._chunks.append(data)

    def text(self) -> str:
        return "".join(self._chunks)


def html_to_text(raw_html: str) -> str:
    """Strip HTML to readable plain text, collapsing whitespace.

    Uses the stdlib parser (no new dependency). Non-breaking spaces and other
    entities are unescaped; runs of whitespace collapse to single spaces so the
    downstream regex extractors see stable, space-separated tokens.
    """
    parser = _TextExtractor()
    parser.feed(raw_html)
    parser.close()
    text = unescape(parser.text())
    # Collapse intra-line whitespace (incl. non-breaking spaces) to single spaces,
    # then squeeze blank lines. Extractors anchor on words, not layout.
    text = re.sub(r"[ \t\xa0​]+", " ", text)
    text = re.sub(r"\s*\n\s*\n+", "\n", text)
    return text.strip()


def list_filings(
    ticker: str,
    *,
    forms: set[str] | None = None,
    since: date | None = None,
    until: date | None = None,
    client: EdgarClient | None = None,
) -> list[FilingRef]:
    """Parse the submissions index for ``ticker`` into filtered ``FilingRef``s.

    ``forms`` filters by form type (normalized by stripping spaces and slashes,
    so "S-4/A" matches "S-4A" and "DEF 14A" matches "DEF14A"). ``since``/``until``
    bound the filing date inclusively. Results are sorted newest-first.
    """
    client = client or EdgarClient()
    cik = client.lookup_cik(ticker)
    subs = client.get_submissions(ticker)
    recent = subs.get("filings", {}).get("recent", {})

    accns = recent.get("accessionNumber", [])
    all_forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    docs = recent.get("primaryDocument", [])

    wanted = {_norm_form(f) for f in forms} if forms else None
    out: list[FilingRef] = []
    for accn, form, filed_str, doc in zip(accns, all_forms, dates, docs, strict=False):
        if wanted is not None and _norm_form(form) not in wanted:
            continue
        filed = date.fromisoformat(filed_str)
        if since is not None and filed < since:
            continue
        if until is not None and filed > until:
            continue
        out.append(
            FilingRef(
                ticker=ticker.upper(),
                cik=cik,
                form=form,
                filed=filed,
                accession=accn,
                primary_document=doc,
            )
        )
    out.sort(key=lambda f: f.filed, reverse=True)
    return out


def _norm_form(form: str) -> str:
    """Normalize a form label for comparison: upper-case, no spaces/slashes."""
    return form.upper().replace(" ", "").replace("/", "")


def _cached_document_path(accession: str, *, documents_dir: Path) -> Path | None:
    """Locate a cached document file by accession number.

    Fixtures are named ``{TICKER}_{FORM}_{ACCESSION}_{DOC}.htm``; matching on the
    accession is stable regardless of the ticker/form/doc spelling.
    """
    matches = sorted(documents_dir.glob(f"*_{accession}_*"))
    return matches[0] if matches else None


def get_document_text(
    ref: FilingRef,
    *,
    documents_dir: Path | str = DOCUMENTS_DIR,
    offline: bool | None = None,
) -> str:
    """Return the plain text of ``ref``'s primary document, offline-first.

    Reads the committed HTML fixture (matched by accession) and strips it to
    text. In OFFLINE mode a missing fixture raises loudly rather than fetching.
    """
    documents_dir = Path(documents_dir)
    is_offline = settings.OFFLINE if offline is None else offline

    path = _cached_document_path(ref.accession, documents_dir=documents_dir)
    if path is not None:
        return html_to_text(path.read_text(encoding="utf-8", errors="ignore"))

    if is_offline:
        raise FileNotFoundError(
            f"offline mode: no cached document for accession {ref.accession} "
            f"under {documents_dir} (would have fetched {ref.url})"
        )

    # Live path — never exercised in CI (documents are always committed). Fetches
    # the HTML with the fair-access User-Agent, then strips to text.
    import requests  # local import so offline runs never require the dep

    resp = requests.get(ref.url, headers={"User-Agent": settings.SEC_USER_AGENT}, timeout=30)
    resp.raise_for_status()
    return html_to_text(resp.text)


def find_documents(
    ticker: str,
    *,
    forms: set[str] | None = None,
    since: date | None = None,
    until: date | None = None,
    documents_dir: Path | str = DOCUMENTS_DIR,
    client: EdgarClient | None = None,
) -> list[tuple[FilingRef, str]]:
    """One-call helper: filtered filings for ``ticker`` paired with their text.

    Only filings whose document is actually cached are returned (offline runs
    silently skip filings with no committed fixture — the submissions index lists
    far more filings than we cache documents for).
    """
    documents_dir = Path(documents_dir)
    client = client or EdgarClient()
    refs = list_filings(ticker, forms=forms, since=since, until=until, client=client)
    out: list[tuple[FilingRef, str]] = []
    for ref in refs:
        path = _cached_document_path(ref.accession, documents_dir=documents_dir)
        if path is None:
            continue
        out.append((ref, html_to_text(path.read_text(encoding="utf-8", errors="ignore"))))
    return out
