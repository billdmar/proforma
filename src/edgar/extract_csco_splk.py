"""Deal-fact & fairness-opinion extraction for deal #2: Cisco / Splunk.

The P6 generality proof — a SECOND real announced US public-public deal run
through the same contracts as deal #1 (Synopsys/ANSYS). This module is a
parallel of :mod:`src.edgar.extract`, retargeted to the Splunk merger proxy;
deal #1's module is left byte-identical.

Source of truth is the Splunk merger proxy — DEFM14A accession
``0001140361-23-050211``, filed 2023-10-30 — parsed from its committed HTML
fixture via :mod:`src.edgar.filings`. Every figure produced here carries a
:class:`~src.schema.DocProvenance` (accession + form + filed date + a
human-locatable section + a verbatim quote), so each disclosed number is
auditable back to the filing (CLAUDE.md: "no unsourced deal facts"). Figures are
located by anchored regexes against the *actual* proxy text; the verbatim quote
in each provenance record is sliced from that same text. Undisclosed figures are
honest ``None`` whose provenance still records where we looked.

Two entry points (deal-#2 names so they never shadow deal #1's exports):
* :func:`extract_deal_terms_csco_splk` -> :class:`~src.schema.DealTerms`
  (Cisco acquires Splunk for $157.00/share in cash — an ALL-CASH deal, so the
  exchange ratio is honestly ``None``).
* :func:`extract_fairness_disclosures_csco_splk` -> list of TWO
  :class:`~src.schema.FairnessDisclosure` records — Splunk had two financial
  advisors, Qatalyst Partners LP and Morgan Stanley & Co. LLC, each with its own
  disclosed methodologies scoped to that advisor's opinion section.
"""

from __future__ import annotations

import re
from datetime import date

from src.edgar.client import EdgarClient
from src.edgar.filings import FilingRef, find_documents
from src.schema import (
    AdvisorMethodology,
    ConsiderationType,
    DealTerms,
    DocProvenance,
    FairnessDisclosure,
    SourcedRange,
    SourcedValue,
)

# --- Deal identity (Cisco/Splunk) ------------------------------------------
# Not in config.settings (that holds deal #1's SNPS/ANSS); these are deal-#2
# constants, each provenance-verified against the cached filings below.
_ACQUIRER_TICKER = "CSCO"
_ACQUIRER_NAME = "Cisco Systems, Inc."
_TARGET_TICKER = "SPLK"
_TARGET_NAME = "Splunk Inc."
# Splunk's CIK is not in the committed SEC ticker index (SPLK dropped from the
# feed after the merger closed), so it is carried as a sourced constant here.
_TARGET_CIK = "0001353283"

# The Splunk merger proxy — the primary deal-fact source.
_DEFM14A_ACCESSION = "0001140361-23-050211"
_DEFM14A_FORM = "DEFM14A"
_DEFM14A_FILED = date(2023, 10, 30)

# Deal announcement date — disclosed in the proxy's "Background of the Merger"
# ("Cisco's desired targeted announcement date of September 21, 2023") and in
# the deal 8-K/425 of the same date. A plain disclosed fact on DealTerms.
_ANNOUNCE_DATE = date(2023, 9, 21)

# Deal COMPLETION date — disclosed in Splunk's merger-completion 8-K (accession
# 0001104659-24-035289, filed 2024-03-18: "On March 18, 2024 (the 'Closing
# Date'), Splunk Inc. ... completed the previously announced transaction with
# Cisco Systems, Inc."). The DEFM14A itself was filed while the deal was pending.
_CLOSE_DATE = date(2024, 3, 18)
_CLOSE_8K_ACCESSION = "0001104659-24-035289"

# En-dash / hyphen used between range endpoints in the proxy tables.
_DASH = r"[–—-]"


class _SplunkClient(EdgarClient):
    """EdgarClient that also resolves Splunk's CIK.

    The base client resolves tickers from the cached SEC ticker index plus deal
    #1's SNPS/ANSS fallback; SPLK is in neither, so we add its sourced CIK here
    (an explicit constant, not a guessed value — honest-provenance rule).
    """

    def lookup_cik(self, ticker: str) -> str:
        if ticker.upper() == _TARGET_TICKER:
            return _TARGET_CIK
        return super().lookup_cik(ticker)


def _defm14a() -> tuple[FilingRef, str]:
    """Return the Splunk DEFM14A (ref, plain text), read from the cached fixture."""
    docs = find_documents(_TARGET_TICKER, forms={_DEFM14A_FORM}, client=_SplunkClient())
    for ref, text in docs:
        if ref.accession == _DEFM14A_ACCESSION:
            return ref, text
    if docs:  # fall back to the newest DEFM14A if the exact accession moved
        return docs[0]
    raise FileNotFoundError(
        f"no cached {_DEFM14A_FORM} for {_TARGET_TICKER} (expected accession {_DEFM14A_ACCESSION})"
    )


def _prov(section: str, quote: str, ref: FilingRef | None = None) -> DocProvenance:
    """Build a DocProvenance stamped to the DEFM14A (or a supplied ref)."""
    accession = ref.accession if ref else _DEFM14A_ACCESSION
    form = ref.form if ref else _DEFM14A_FORM
    filed = ref.filed if ref else _DEFM14A_FILED
    url = ref.url if ref else None
    return DocProvenance(
        accession=accession,
        form=form,
        filed=filed,
        section=section,
        quote=quote.strip(),
        url=url,
    )


def _quote_around(text: str, match: re.Match, before: int = 40, after: int = 140) -> str:
    """Slice a verbatim snippet around a regex match for provenance."""
    start = max(0, match.start() - before)
    end = min(len(text), match.end() + after)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def _clean_num(raw: str) -> float:
    """Parse a proxy-formatted number ('168,536,732', '157.00', '$ 4,038') to float."""
    return float(raw.replace(",", "").replace("$", "").strip())


# ===========================================================================
# Deal terms
# ===========================================================================
def extract_deal_terms_csco_splk(
    text: str | None = None, ref: FilingRef | None = None
) -> DealTerms:
    """Extract the disclosed transaction terms from the Splunk DEFM14A.

    Cisco/Splunk is an ALL-CASH deal: $157.00 per Splunk share, so
    ``exchange_ratio`` and ``reference_acquirer_price`` are honest ``None`` (no
    stock leg to value). Every populated figure carries a verbatim-quoted
    DocProvenance; undisclosed figures are honest ``None``.
    """
    if text is None:
        ref, text = _defm14a()

    # --- Merger consideration: $157.00 per share, all cash.
    m = re.search(
        r"\$([0-9]+\.[0-9]{2})\s+in cash.{0,80}?for each share of Splunk common stock",
        text,
        re.DOTALL,
    )
    cash_per_share = None
    if m:
        cash_per_share = SourcedValue(
            value=_clean_num(m.group(1)),
            provenance=_prov(
                "The Merger — Merger Consideration",
                _quote_around(text, m, before=60, after=20),
                ref,
            ),
            unit="USD/share",
            label="Per-share cash consideration",
        )

    # --- Stated/headline per-share deal value. For an all-cash deal the stated
    # per-share price is the cash amount itself ("Per Share Merger Consideration
    # of $157.00 in cash").
    m = re.search(
        r"Per Share Merger Consideration of \$([0-9]+\.[0-9]{2}) in cash",
        text,
    )
    stated_price = None
    if m:
        stated_price = SourcedValue(
            value=_clean_num(m.group(1)),
            provenance=_prov(
                "The Merger — Merger Consideration",
                _quote_around(text, m, before=60, after=40),
                ref,
            ),
            unit="USD/share",
            label="Headline per-share merger consideration (all cash)",
        )

    # --- Premium: ~31% over Splunk's $119.59 unaffected close (Sept 20, 2023).
    m = re.search(
        r"premium of approximately ([0-9]{1,2})% over Splunk.s closing stock price of "
        r"\$([0-9]+\.[0-9]{2}) on (September [0-9]{1,2}, 20[0-9]{2})",
        text,
    )
    premium_pct = premium_ref = None
    if m:
        quote = _quote_around(text, m, before=60, after=120)
        premium_pct = SourcedValue(
            value=_clean_num(m.group(1)),
            provenance=_prov("The Merger — Recommendation / Reasons", quote, ref),
            unit="percent",
            label=f"Premium over unaffected ({m.group(3)}) closing price",
        )
        premium_ref = SourcedValue(
            value=_clean_num(m.group(2)),
            provenance=_prov("The Merger — Recommendation / Reasons", quote, ref),
            unit="USD/share",
            label=f"Splunk unaffected closing price ({m.group(3)})",
        )

    # --- Target shares outstanding (record date).
    m = re.search(
        r"there were ([0-9,]+) shares of Splunk common stock outstanding",
        text,
    )
    tgt_shares = None
    if m:
        tgt_shares = SourcedValue(
            value=_clean_num(m.group(1)),
            provenance=_prov(
                "The Special Meeting — Record Date and Quorum",
                _quote_around(text, m, before=40, after=40),
                ref,
            ),
            unit="shares",
            label="Splunk shares outstanding as of the record date",
        )

    # --- Disclosed annual synergies: the proxy discusses strategic rationale
    # qualitatively but discloses no quantified annual synergy run-rate. Honest
    # None with provenance noting the search (our own cases live in ASSUMPTIONS).
    synergies = SourcedValue(
        value=None,
        provenance=_prov(
            "Searched: Reasons for the Merger / Background / Opinions of Financial Advisors",
            "no quantified annual synergy run-rate is disclosed in the proxy; "
            "the strategic rationale is described only qualitatively",
            ref,
        ),
        unit="USD",
        label="Disclosed annual synergy run-rate (not quantified in proxy)",
    )

    return DealTerms(
        acquirer_ticker=_ACQUIRER_TICKER,
        target_ticker=_TARGET_TICKER,
        acquirer_name=_ACQUIRER_NAME,
        target_name=_TARGET_NAME,
        announce_date=_ANNOUNCE_DATE,
        close_date=_CLOSE_DATE,  # disclosed in the completion 8-K (see _CLOSE_8K_ACCESSION)
        consideration_type=ConsiderationType.CASH,
        cash_per_share=cash_per_share,
        exchange_ratio=None,  # all-cash deal: no stock leg (honest None)
        stated_price_per_share=stated_price,
        reference_acquirer_price=None,  # no stock leg to value (honest None)
        premium_pct=premium_pct,
        premium_reference_price=premium_ref,
        disclosed_synergies_annual=synergies,
        target_shares_outstanding=tgt_shares,
        notes=(
            "Terms extracted from the Splunk DEFM14A (accession "
            f"{_DEFM14A_ACCESSION}, filed {_DEFM14A_FILED}). Cisco acquired Splunk "
            "for $157.00 per share in cash (all-cash); the ~31% premium is quoted "
            "over the Sept 20, 2023 unaffected close of $119.59. Deal completed "
            f"{_CLOSE_DATE} per Splunk's 8-K (accession {_CLOSE_8K_ACCESSION})."
        ),
    )


# ===========================================================================
# Fairness opinions — Qatalyst Partners AND Morgan Stanley (both advise Splunk)
# ===========================================================================
def _section(text: str, start_anchor: str, end_anchors: list[str]) -> str:
    """Return the substring from ``start_anchor`` to the first ``end_anchor``."""
    i = text.find(start_anchor)
    if i < 0:
        return ""
    j = len(text)
    for anchor in end_anchors:
        k = text.find(anchor, i + len(start_anchor))
        if 0 <= k < j:
            j = k
    return text[i:j]


# Forecast-scenario labels that head the implied-per-share rows in both
# advisors' tables. An optional leading "N.Nx–N.Nx" multiple column is skipped;
# per-share endpoints are bounded to 1–3 integer digits so a trailing page
# number (e.g. "263" abutting "57") is never swallowed.
_SCENARIO_LABELS = (
    r"(Sensitivity 1 Projections|Sensitivity 2 Projections|"
    r"Baseline Management Projections|Street Estimates|Management Sensitivities|"
    r"Research Case \(Reference Only\)|Sensitivity Projections)"
)
_SCENARIO_ROW = re.compile(
    _SCENARIO_LABELS
    + r"(?:\(1\))?\s+"
    + r"(?:[0-9.]+x\s*"
    + _DASH
    + r"\s*[0-9.]+x\s+)?"
    + r"([0-9]{1,3}(?:\.[0-9]{2})?)\s*"
    + _DASH
    + r"\s*([0-9]{1,3}(?:\.[0-9]{2})?)"
)


def _scenario_rows(section: str) -> dict[str, tuple[float, float]]:
    """Parse '<Scenario> [mult range] low–high' implied per-share rows.

    Keyed by an ordinal so repeated scenario labels (e.g. a revenue table and an
    LFCF table both listing "Baseline Management Projections") are all retained.
    """
    rows: dict[str, tuple[float, float]] = {}
    for i, m in enumerate(_SCENARIO_ROW.finditer(section)):
        rows[f"{m.group(1)} [{i}]"] = (_clean_num(m.group(2)), _clean_num(m.group(3)))
    return rows


def _inline_ranges(section: str) -> list[tuple[float, float]]:
    """Parse inline 'a range of values ... of approximately $lo to $hi per share'."""
    return [
        (_clean_num(m.group(1)), _clean_num(m.group(2)))
        for m in re.finditer(
            r"of approximately \$([0-9]+\.[0-9]{2}) to \$([0-9]+\.[0-9]{2}) per share",
            section,
        )
    ]


def _union_range(pairs: list[tuple[float, float]]) -> tuple[float | None, float | None]:
    if not pairs:
        return None, None
    return min(lo for lo, _ in pairs), max(hi for _, hi in pairs)


def _multiple_range(
    section: str, phrase: str, key: str, label: str, prov_section: str, ref: FilingRef | None
) -> tuple[str, SourcedRange] | None:
    """Extract a single disclosed representative multiple range by anchor phrase."""
    m = re.search(
        re.escape(phrase) + r"\s+([0-9.]+)x\s*(?:to|" + _DASH + r")\s*([0-9.]+)x",
        section,
    )
    if not m:
        return None
    return key, SourcedRange(
        low=_clean_num(m.group(1)),
        high=_clean_num(m.group(2)),
        provenance=_prov(prov_section, _quote_around(section, m, before=40, after=40), ref),
        unit="x",
        label=label,
    )


def _dcf_assumptions(
    section: str, prov_section: str, ref: FilingRef | None
) -> dict[str, SourcedRange]:
    """Discount-rate and perpetuity/perpetual-growth ranges for a DCF section."""
    assumptions: dict[str, SourcedRange] = {}
    m = re.search(
        r"discount rate[s]? (?:of|ranging from) ([0-9.]+)(?:%| percent) to ([0-9.]+)(?:%| percent)",
        section,
    )
    if m:
        assumptions["discount_rate"] = SourcedRange(
            low=_clean_num(m.group(1)),
            high=_clean_num(m.group(2)),
            provenance=_prov(prov_section, _quote_around(section, m, before=30, after=40), ref),
            unit="percent",
            label="Estimated WACC / discount-rate range",
        )
    m = re.search(
        r"(?:perpetuity growth rate range of|perpetual growth rates of) "
        r"([0-9.]+)(?:%| percent) to ([0-9.]+)(?:%| percent)",
        section,
    )
    if m:
        assumptions["perpetuity_growth"] = SourcedRange(
            low=_clean_num(m.group(1)),
            high=_clean_num(m.group(2)),
            provenance=_prov(prov_section, _quote_around(section, m, before=20, after=40), ref),
            unit="percent",
            label="Terminal-value perpetuity growth-rate range",
        )
    return assumptions


def _methodology(
    method: str,
    pairs: list[tuple[float, float]],
    prov_section: str,
    quote: str,
    ref: FilingRef | None,
    assumptions: dict[str, SourcedRange],
    implied_label: str,
    notes: str,
) -> AdvisorMethodology:
    lo, hi = _union_range(pairs)
    return AdvisorMethodology(
        method=method,
        implied_range=SourcedRange(
            low=lo,
            high=hi,
            provenance=_prov(prov_section, quote, ref),
            unit="USD/share",
            label=implied_label,
        ),
        assumptions=assumptions,
        notes=notes,
    )


def _qatalyst(text: str, ref: FilingRef | None) -> list[AdvisorMethodology]:
    """Qatalyst Partners' three disclosed methodologies, scoped to its opinion."""
    methods: list[AdvisorMethodology] = []

    # --- Discounted Cash Flow --------------------------------------------
    dcf = _section(text, "Discounted Cash Flow Analysis Qatalyst", ["Selected Companies Analysis"])
    if dcf:
        rows = _scenario_rows(dcf)
        prov_sec = "Opinion of Qatalyst Partners — Discounted Cash Flow Analysis"
        methods.append(
            _methodology(
                "Discounted Cash Flow",
                list(rows.values()),
                prov_sec,
                _quote_around(
                    dcf, re.search(r"implied a range of values", dcf), before=10, after=200
                )
                if re.search(r"implied a range of values", dcf)
                else "",
                ref,
                _dcf_assumptions(dcf, prov_sec, ref),
                "Implied per-share range (union across Baseline / Sensitivity 1 / Sensitivity 2)",
                "Per-scenario implied ranges: "
                + "; ".join(
                    f"{k.rsplit(' [', 1)[0]}: {v[0]:.2f}–{v[1]:.2f}" for k, v in rows.items()
                )
                + ". UFCF discounted Q3 FY2024–FY2034 with an FY2034 terminal value.",
            )
        )

    # --- Selected Companies ----------------------------------------------
    selcomp = _section(
        text, "Selected Companies Analysis Qatalyst", ["Selected Transactions Analysis"]
    )
    if selcomp:
        rows = _scenario_rows(selcomp)
        prov_sec = "Opinion of Qatalyst Partners — Selected Companies Analysis"
        assumptions: dict[str, SourcedRange] = {}
        for phrase, key, label in (
            (
                "representative multiple range of",
                "cy2024e_revenue_multiple",
                "Representative CY2024E revenue multiple range",
            ),
        ):
            got = _multiple_range(selcomp, phrase, key, label, prov_sec, ref)
            if got:
                assumptions[got[0]] = got[1]
        methods.append(
            _methodology(
                "Selected Companies",
                list(rows.values()),
                prov_sec,
                _quote_around(
                    selcomp, re.search(r"implied a range of values", selcomp), before=10, after=200
                )
                if re.search(r"implied a range of values", selcomp)
                else "",
                ref,
                assumptions,
                "Implied per-share range (union across EV/CY2024E-revenue and "
                "equity-value/CY2024E-LFCF multiple tables)",
                "Union of the two public-trading-multiple tables (revenue and LFCF), "
                "each across Street Estimates / Management Sensitivities / Baseline.",
            )
        )

    # --- Selected Transactions -------------------------------------------
    seltxn = _section(text, "Selected Transactions Analysis Qatalyst", ["Miscellaneous"])
    if seltxn:
        pairs = _inline_ranges(seltxn)
        prov_sec = "Opinion of Qatalyst Partners — Selected Transactions Analysis"
        m = re.search(r"implied a range of values", seltxn)
        methods.append(
            _methodology(
                "Selected Transactions",
                pairs,
                prov_sec,
                _quote_around(seltxn, m, before=10, after=120) if m else "",
                ref,
                {},
                "Implied per-share range (union across NTM revenue, NTM EBITDA and "
                "NTM LFCF sub-analyses)",
                "Three sub-analyses: NTM revenue 4.5x–8.0x -> 97.37–178.26; "
                "NTM EBITDA 18.0x–34.0x -> 88.22–172.96; NTM LFCF 20.0x–32.0x -> "
                "107.27–171.63.",
            )
        )
    return methods


def _morgan_stanley(text: str, ref: FilingRef | None) -> list[AdvisorMethodology]:
    """Morgan Stanley's three disclosed methodologies, scoped to its opinion."""
    methods: list[AdvisorMethodology] = []

    # --- Discounted Cash Flow --------------------------------------------
    dcf = _section(text, "Discounted Cash Flow Analysis Morgan Stanley", ["Precedent Transactions"])
    if dcf:
        rows = _scenario_rows(dcf)
        prov_sec = "Opinion of Morgan Stanley — Discounted Cash Flow Analysis"
        m = re.search(r"implied value per share", dcf)
        methods.append(
            _methodology(
                "Discounted Cash Flow",
                list(rows.values()),
                prov_sec,
                _quote_around(dcf, m, before=10, after=200) if m else "",
                ref,
                _dcf_assumptions(dcf, prov_sec, ref),
                "Implied per-share range (union across Baseline / Sensitivity 1 / Sensitivity 2)",
                "Per-scenario implied ranges: "
                + "; ".join(
                    f"{k.rsplit(' [', 1)[0]}: {v[0]:.2f}–{v[1]:.2f}" for k, v in rows.items()
                )
                + ". UFCF for CY2023–CY2033 discounted to Sept 19, 2023.",
            )
        )

    # --- Public Trading Comparables --------------------------------------
    pubtrade = _section(
        text, "Public Trading Comparables Analysis Morgan Stanley", ["Discounted Equity Value"]
    )
    if pubtrade:
        rows = _scenario_rows(pubtrade)
        prov_sec = "Opinion of Morgan Stanley — Public Trading Comparables Analysis"
        m = re.search(r"implied value per share", pubtrade)
        methods.append(
            _methodology(
                "Public Trading Comparables",
                list(rows.values()),
                prov_sec,
                _quote_around(pubtrade, m, before=10, after=200) if m else "",
                ref,
                {},
                "Implied per-share range (union across P/CY2024E-LFCF 15.0x–25.0x and "
                "AV/CY2024E-revenue 4.0x–6.0x tables)",
                "Union across the two comparables tables (LFCF and revenue), each over "
                "Research Case / Sensitivity / Baseline.",
            )
        )

    # --- Precedent Transactions ------------------------------------------
    precedent = _section(
        text,
        "Precedent Transactions Multiples Analysis Morgan Stanley",
        ["Equity Research Analysts", "Analyst Price Targets", "Equity Research"],
    )
    if precedent:
        rows = _scenario_rows(precedent)
        prov_sec = "Opinion of Morgan Stanley — Precedent Transactions Multiples Analysis"
        m = re.search(r"summarizes the results", precedent) or re.search(
            r"Implied Value Per Share", precedent
        )
        methods.append(
            _methodology(
                "Precedent Transactions",
                list(rows.values()),
                prov_sec,
                _quote_around(precedent, m, before=10, after=200) if m else "",
                ref,
                {},
                "Implied per-share range (union across P/NTM-LFCF 20.0x–40.0x and "
                "AV/NTM-revenue 4.0x–8.0x tables)",
                "Selected technology transactions > $5B since 2011; union across the "
                "LFCF and revenue multiple tables (Research / Sensitivity / Baseline).",
            )
        )
    return methods


def extract_fairness_disclosures_csco_splk(
    text: str | None = None, ref: FilingRef | None = None
) -> list[FairnessDisclosure]:
    """Extract BOTH Splunk advisors' disclosed fairness analyses from the DEFM14A.

    Returns two :class:`FairnessDisclosure` records — Qatalyst Partners and
    Morgan Stanley — each scoped to its own opinion section so implied ranges are
    never cross-attributed. Both advised Splunk; each has a DCF plus two
    market-multiple methodologies with disclosed assumption and implied ranges,
    every figure provenance-stamped and quoted from the proxy.
    """
    if text is None:
        ref, text = _defm14a()

    # Scope each advisor to its own opinion section. The opinion headings recur
    # in the table of contents and the summary; the *analysis* bodies are the
    # last occurrences (rfind). Qatalyst's opinion precedes Morgan Stanley's, so
    # the Qatalyst window ends where Morgan Stanley's opinion body begins.
    qat_start = text.rfind("Opinion of Qatalyst Partners LP")
    ms_start = text.rfind("Opinion of Morgan Stanley & Co. LLC")
    qat_text = text[qat_start:ms_start] if 0 <= qat_start < ms_start else text
    ms_text = text[ms_start:] if ms_start >= 0 else text

    projections = _extract_management_projections(text, ref)
    dt = extract_deal_terms_csco_splk(text, ref)
    offered = dt.stated_price_per_share

    qatalyst = FairnessDisclosure(
        advisor="Qatalyst Partners",
        represents=_TARGET_TICKER,
        methodologies=_qatalyst(qat_text, ref),
        management_projections=projections,
        offered_consideration=offered,
        notes=(
            "Qatalyst Partners LP served as a financial advisor to Splunk. Three "
            "disclosed methodologies (DCF, Selected Companies, Selected "
            "Transactions); implied ranges compared to the $157.00 all-cash "
            f"consideration. Extracted from the Splunk DEFM14A (accession {_DEFM14A_ACCESSION})."
        ),
    )
    morgan_stanley = FairnessDisclosure(
        advisor="Morgan Stanley",
        represents=_TARGET_TICKER,
        methodologies=_morgan_stanley(ms_text, ref),
        management_projections=projections,
        offered_consideration=offered,
        notes=(
            "Morgan Stanley & Co. LLC served as a financial advisor to Splunk. "
            "Three disclosed methodologies (DCF, Public Trading Comparables, "
            "Precedent Transactions); implied ranges compared to the $157.00 "
            f"all-cash consideration. Extracted from the Splunk DEFM14A (accession {_DEFM14A_ACCESSION})."
        ),
    )
    return [qatalyst, morgan_stanley]


def _extract_management_projections(
    text: str, ref: FilingRef | None
) -> dict[str, list[SourcedValue]]:
    """Capture the Baseline Management Projections Revenue & UFCF rows.

    FY2024E–FY2034E, from the "Summary of Management Projections" table (the two
    advisors relied on the same projections). Values in USD millions as disclosed
    (label notes the scale); each is provenance-stamped to the projections table.
    """
    projections: dict[str, list[SourcedValue]] = {}
    # Bound the block to the Baseline block so Sensitivity rows aren't captured.
    block = _section(
        text,
        "Baseline Management Projections Revenue",
        ["Sensitivity 1 Projections"],
    )
    if not block:
        return projections

    def _row(label_pat: str, metric: str, key: str) -> None:
        m = re.search(label_pat + r"\s+((?:\(?\$[0-9,]+\)? ?)+)", block)
        if not m:
            return
        nums = re.findall(r"\$([0-9,]+)", m.group(1))
        quote = _quote_around(block, m, before=30, after=10)
        prov = _prov(
            "Summary of Management Projections — Baseline Management Projections",
            quote,
            ref,
        )
        projections[key] = [
            SourcedValue(
                value=_clean_num(n),
                provenance=prov,
                unit="USD millions",
                label=f"{metric} (Baseline Management Projections, FY{2024 + i}E)",
            )
            for i, n in enumerate(nums)
        ]

    # "Baseline Management Projections Revenue" is the section anchor, so the
    # revenue row is matched from the block start (empty label prefix).
    _row(r"", "Revenue", "revenue")
    _row(r"Unlevered Free Cash Flow ?\(2\)", "Unlevered Free Cash Flow", "unlevered_free_cash_flow")
    return projections
