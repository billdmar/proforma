"""Deal-fact & fairness-opinion extraction from the merger proxy (DEFM14A).

NET-NEW for proforma. Every figure produced here carries a
:class:`~src.schema.DocProvenance` (accession + form + filed date + a
human-locatable section + a verbatim quote), so each disclosed number is
auditable back to the filing (CLAUDE.md: "no unsourced deal facts").

Source of truth is the ANSYS merger proxy — DEFM14A accession
``0001140361-24-020334``, filed 2024-04-17 — parsed from its committed HTML
fixture via :mod:`src.edgar.filings`. Figures are located by anchored regexes
against the *actual* proxy text (so the extraction is genuinely sourced, not
hand-typed); the verbatim quote in each provenance record is sliced from that
same text. Where the proxy does not disclose a figure (e.g. a quantified annual
synergy run-rate), the value is an honest ``None`` whose provenance still records
where we looked.

Two entry points:
* :func:`extract_deal_terms` -> :class:`~src.schema.DealTerms`
* :func:`extract_fairness_disclosures` -> list of
  :class:`~src.schema.FairnessDisclosure` (Qatalyst Partners, advisor to ANSYS)
"""

from __future__ import annotations

import re
from datetime import date

from config import settings

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

# The ANSYS merger proxy — the primary deal-fact source.
_DEFM14A_ACCESSION = "0001140361-24-020334"
_DEFM14A_FORM = "DEFM14A"
_DEFM14A_FILED = date(2024, 4, 17)

# Deal announcement date (Synopsys/ANSYS, disclosed in the deal 8-K/425 of the
# same date and throughout the proxy's "Background of the Merger"). A plain
# disclosed fact carried on DealTerms.announce_date.
_ANNOUNCE_DATE = date(2024, 1, 16)

# En-dash / hyphen used between range endpoints in the proxy tables.
_DASH = r"[–—-]"


def _defm14a() -> tuple[FilingRef, str]:
    """Return the ANSYS DEFM14A (ref, plain text), read from the cached fixture."""
    docs = find_documents(settings.TARGET_TICKER, forms={_DEFM14A_FORM})
    for ref, text in docs:
        if ref.accession == _DEFM14A_ACCESSION:
            return ref, text
    if docs:  # fall back to the newest DEFM14A if the exact accession moved
        return docs[0]
    raise FileNotFoundError(
        f"no cached {_DEFM14A_FORM} for {settings.TARGET_TICKER} "
        f"(expected accession {_DEFM14A_ACCESSION})"
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
    """Parse a proxy-formatted number ('2,510', '303.33', '$ 795') to float."""
    return float(raw.replace(",", "").replace("$", "").strip())


# ===========================================================================
# Deal terms
# ===========================================================================
def extract_deal_terms(text: str | None = None, ref: FilingRef | None = None) -> DealTerms:
    """Extract the disclosed transaction terms from the ANSYS DEFM14A.

    Programmatically located against the proxy text; every populated figure
    carries a verbatim-quoted DocProvenance. Undisclosed figures are honest
    ``None`` with provenance noting where we looked.
    """
    if text is None:
        ref, text = _defm14a()

    # --- Merger consideration: $197.00 cash + 0.3450 SNPS share per ANSS share.
    m = re.search(
        r"\$([0-9]+\.[0-9]{2})\s+in cash.{0,160}?([0-9]\.[0-9]{3,4})\s+of a share of Synopsys",
        text,
        re.DOTALL,
    )
    cash_per_share = exchange_ratio = None
    if m:
        quote = _quote_around(text, m, before=60, after=40)
        cash_per_share = SourcedValue(
            value=_clean_num(m.group(1)),
            provenance=_prov("The Merger — Merger Consideration", quote, ref),
            unit="USD/share",
            label="Per-share cash consideration",
        )
        exchange_ratio = SourcedValue(
            value=_clean_num(m.group(2)),
            provenance=_prov("The Merger — Merger Consideration", quote, ref),
            unit="ratio",
            label="Exchange ratio (Synopsys shares per Ansys share)",
        )

    # --- Stated/implied per-share deal value on the unaffected date (Dec 21, 2023).
    m = re.search(
        r"merger consideration represented approximately \$([0-9]+\.[0-9]{2}) in value",
        text,
    )
    stated_price = None
    if m:
        stated_price = SourcedValue(
            value=_clean_num(m.group(1)),
            provenance=_prov(
                "The Merger — Background / Implied Value of Merger Consideration",
                _quote_around(text, m, before=200, after=20),
                ref,
            ),
            unit="USD/share",
            label="Implied per-share merger consideration value at Dec 21, 2023 (unaffected)",
        )

    # --- Reference acquirer (Synopsys) price used to value the stock leg.
    m = re.search(
        r"NASDAQ, on December 21, 2023.{0,140}?of \$([0-9]+\.[0-9]{2})",
        text,
    )
    ref_acq_price = None
    if m:
        ref_acq_price = SourcedValue(
            value=_clean_num(m.group(1)),
            provenance=_prov(
                "The Merger — Implied Value of Merger Consideration",
                _quote_around(text, m, before=120, after=40),
                ref,
            ),
            unit="USD/share",
            label="Synopsys closing price on Dec 21, 2023 (unaffected date)",
        )

    # --- Premium: 29% over the $303.16 unaffected ANSS close.
    m = re.search(
        r"a ([0-9]{1,2})% premium over the closing price of \$([0-9]+\.[0-9]{2})",
        text,
    )
    premium_pct = premium_ref = None
    if m:
        quote = _quote_around(text, m, before=120, after=120)
        premium_pct = SourcedValue(
            value=_clean_num(m.group(1)),
            provenance=_prov("The Merger — Recommendation / Reasons", quote, ref),
            unit="percent",
            label="Premium over unaffected (Dec 21, 2023) closing price",
        )
        premium_ref = SourcedValue(
            value=_clean_num(m.group(2)),
            provenance=_prov("The Merger — Recommendation / Reasons", quote, ref),
            unit="USD/share",
            label="Ansys unaffected closing price (Dec 21, 2023)",
        )

    # --- Target shares outstanding (record date).
    m = re.search(
        r"Ansys had ([0-9,]+) shares of Ansys common stock and no shares of preferred",
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
            label="Ansys shares outstanding as of the record date",
        )

    # --- Disclosed annual synergies: the proxy discusses synergies qualitatively
    # but discloses no quantified annual run-rate. Honest None with provenance
    # noting the search (our own synergy cases live in DealAssumptions/ASSUMPTIONS).
    synergies = SourcedValue(
        value=None,
        provenance=_prov(
            "Searched: Reasons for the Merger / Background / Opinion of Financial Advisor",
            "no quantified annual synergy run-rate is disclosed in the proxy; "
            "synergies are referenced only qualitatively",
            ref,
        ),
        unit="USD",
        label="Disclosed annual synergy run-rate (not quantified in proxy)",
    )

    return DealTerms(
        acquirer_ticker=settings.ACQUIRER_TICKER,
        target_ticker=settings.TARGET_TICKER,
        acquirer_name=settings.ACQUIRER_NAME,
        target_name=settings.TARGET_NAME,
        announce_date=_ANNOUNCE_DATE,
        close_date=None,  # pending as of the DEFM14A
        consideration_type=ConsiderationType.MIXED,
        cash_per_share=cash_per_share,
        exchange_ratio=exchange_ratio,
        stated_price_per_share=stated_price,
        reference_acquirer_price=ref_acq_price,
        premium_pct=premium_pct,
        premium_reference_price=premium_ref,
        disclosed_synergies_annual=synergies,
        target_shares_outstanding=tgt_shares,
        notes=(
            "Terms extracted from the ANSYS DEFM14A (accession "
            f"{_DEFM14A_ACCESSION}, filed {_DEFM14A_FILED}). Consideration is "
            "mixed cash-and-stock; implied value and premium are quoted on the "
            "Dec 21, 2023 unaffected date."
        ),
    )


# ===========================================================================
# Fairness opinion — Qatalyst Partners (advisor to ANSYS)
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


def _case_rows(section: str) -> dict[str, tuple[float, float]]:
    """Parse 'Management Case N  low – high' (and 'Street Case') implied ranges."""
    rows: dict[str, tuple[float, float]] = {}
    for m in re.finditer(
        r"((?:Management Case [123])|Street Case)\s+([0-9]+\.[0-9]{2})\s*"
        + _DASH
        + r"\s*([0-9]+\.[0-9]{2})",
        section,
    ):
        rows[m.group(1)] = (_clean_num(m.group(2)), _clean_num(m.group(3)))
    return rows


def _union_range(rows: dict[str, tuple[float, float]]) -> tuple[float | None, float | None]:
    if not rows:
        return None, None
    lows = [lo for lo, _ in rows.values()]
    highs = [hi for _, hi in rows.values()]
    return min(lows), max(highs)


def extract_fairness_disclosures(
    text: str | None = None, ref: FilingRef | None = None
) -> list[FairnessDisclosure]:
    """Extract Qatalyst Partners' disclosed fairness analyses from the DEFM14A.

    Captures the three disclosed methodologies — Discounted Cash Flow, Selected
    Companies, Selected Transactions — each with its disclosed assumption ranges
    (discount rate, terminal/representative multiples) and the implied per-share
    range it produced, plus Management Case 1 revenue & UFCF projections. Every
    figure is provenance-stamped and quoted from the proxy.
    """
    if text is None:
        ref, text = _defm14a()

    methodologies: list[AdvisorMethodology] = []

    # --- Discounted Cash Flow Analysis -----------------------------------
    dcf = _section(
        text,
        "Discounted Cash Flow Analysis Qatalyst",
        ["Selected Companies Analysis"],
    )
    if dcf:
        dcf_rows = _case_rows(dcf)
        lo, hi = _union_range(dcf_rows)
        assumptions: dict[str, SourcedRange] = {}
        m = re.search(r"discount rates of ([0-9.]+)% to ([0-9.]+)%", dcf)
        if m:
            assumptions["discount_rate"] = SourcedRange(
                low=_clean_num(m.group(1)),
                high=_clean_num(m.group(2)),
                provenance=_prov(
                    "Opinion of Qatalyst Partners — Discounted Cash Flow Analysis",
                    _quote_around(dcf, m, before=30, after=60),
                    ref,
                ),
                unit="percent",
                label="Estimated WACC / discount-rate range",
            )
        m = re.search(r"UFCF multiples of ([0-9.]+)x to ([0-9.]+)x", dcf)
        if m:
            assumptions["ntm_ufcf_multiple"] = SourcedRange(
                low=_clean_num(m.group(1)),
                high=_clean_num(m.group(2)),
                provenance=_prov(
                    "Opinion of Qatalyst Partners — Discounted Cash Flow Analysis",
                    _quote_around(dcf, m, before=40, after=80),
                    ref,
                ),
                unit="x",
                label=(
                    "NTM UFCF terminal multiple (20.0x–30.0x for Mgmt Cases 1 & 2; "
                    "15.0x–25.0x for Mgmt Case 3)"
                ),
            )
        implied_quote = _quote_around(
            dcf,
            re.search(
                r"implied a range of values.*?Management Case 3\s+[0-9.]+\s*"
                + _DASH
                + r"\s*[0-9.]+",
                dcf,
                re.DOTALL,
            )
            or re.search(r"Management Case 1", dcf),
            before=10,
            after=10,
        )
        methodologies.append(
            AdvisorMethodology(
                method="Discounted Cash Flow",
                implied_range=SourcedRange(
                    low=lo,
                    high=hi,
                    provenance=_prov(
                        "Opinion of Qatalyst Partners — Discounted Cash Flow Analysis",
                        implied_quote,
                        ref,
                    ),
                    unit="USD/share",
                    label="Implied per-share range (union across Management Cases 1–3)",
                ),
                assumptions=assumptions,
                notes=(
                    "Per-case implied ranges: "
                    + "; ".join(f"{k}: {v[0]:.2f}–{v[1]:.2f}" for k, v in dcf_rows.items())
                    + ". UFCF discounted CY2024–CY2032 with a FY2033 terminal value."
                ),
            )
        )

    # --- Selected Companies Analysis -------------------------------------
    selcomp = _section(
        text,
        "Selected Companies Analysis Qatalyst",
        ["Selected Transactions Analysis"],
    )
    if selcomp:
        sc_rows = _case_rows(selcomp)
        lo, hi = _union_range(sc_rows)
        assumptions = {}
        m = re.search(r"representative multiple range of ([0-9.]+)x (?:to|and) ([0-9.]+)x", selcomp)
        if m:
            assumptions["cy2024e_lfcf_multiple"] = SourcedRange(
                low=_clean_num(m.group(1)),
                high=_clean_num(m.group(2)),
                provenance=_prov(
                    "Opinion of Qatalyst Partners — Selected Companies Analysis",
                    _quote_around(selcomp, m, before=30, after=60),
                    ref,
                ),
                unit="x",
                label="Representative CY2024E LFCF multiple range",
            )
        methodologies.append(
            AdvisorMethodology(
                method="Selected Companies",
                implied_range=SourcedRange(
                    low=lo,
                    high=hi,
                    provenance=_prov(
                        "Opinion of Qatalyst Partners — Selected Companies Analysis",
                        _quote_around(
                            selcomp, re.search(r"Management Case 1", selcomp), before=60, after=60
                        ),
                        ref,
                    ),
                    unit="USD/share",
                    label="Implied per-share range (union across cases + street case)",
                ),
                assumptions=assumptions,
                notes=(
                    "Per-case implied ranges: "
                    + "; ".join(f"{k}: {v[0]:.2f}–{v[1]:.2f}" for k, v in sc_rows.items())
                ),
            )
        )

    # --- Selected Transactions Analysis ----------------------------------
    seltxn = _section(
        text,
        "Selected Transactions Analysis Qatalyst",
        ["Miscellaneous", "Certain Unaudited", "General"],
    )
    if seltxn:
        assumptions = {}
        m = re.search(r"representative multiple range of ([0-9.]+)x (?:to|and) ([0-9.]+)x", seltxn)
        if m:
            assumptions["ntm_lfcf_multiple"] = SourcedRange(
                low=_clean_num(m.group(1)),
                high=_clean_num(m.group(2)),
                provenance=_prov(
                    "Opinion of Qatalyst Partners — Selected Transactions Analysis",
                    _quote_around(seltxn, m, before=30, after=60),
                    ref,
                ),
                unit="x",
                label="Representative NTM LFCF multiple range",
            )
        m = re.search(
            r"implied a range of values for Ansys common stock of approximately \$([0-9.]+) to \$([0-9.]+)",
            seltxn,
        )
        st_lo = st_hi = None
        st_quote = ""
        if m:
            st_lo, st_hi = _clean_num(m.group(1)), _clean_num(m.group(2))
            st_quote = _quote_around(seltxn, m, before=40, after=20)
        methodologies.append(
            AdvisorMethodology(
                method="Selected Transactions",
                implied_range=SourcedRange(
                    low=st_lo,
                    high=st_hi,
                    provenance=_prov(
                        "Opinion of Qatalyst Partners — Selected Transactions Analysis",
                        st_quote,
                        ref,
                    ),
                    unit="USD/share",
                    label="Implied per-share range (street case, 27 precedent transactions)",
                ),
                assumptions=assumptions,
                notes="Based on NTM LFCF multiples of 27 selected software transactions.",
            )
        )

    # --- Management projections (Management Case 1 revenue & UFCF) ---------
    projections = _extract_management_projections(text, ref)

    # --- Offered consideration the ranges are compared against ($197 + 0.3450 SNPS).
    dt = extract_deal_terms(text, ref)
    offered = dt.stated_price_per_share

    disclosure = FairnessDisclosure(
        advisor="Qatalyst Partners",
        represents=settings.TARGET_TICKER,
        methodologies=methodologies,
        management_projections=projections,
        offered_consideration=offered,
        notes=(
            "Qatalyst Partners served as financial advisor to Ansys. Three "
            "disclosed methodologies; implied ranges compared to the merger "
            "consideration. Extracted from the ANSYS DEFM14A "
            f"(accession {_DEFM14A_ACCESSION})."
        ),
    )
    return [disclosure]


def _extract_management_projections(
    text: str, ref: FilingRef | None
) -> dict[str, list[SourcedValue]]:
    """Capture Management Case 1 Revenue & Unlevered Free Cash Flow projections.

    FY2024E–FY2033E, from the "Certain Unaudited Prospective Financial
    Information" table. Values in USD millions as disclosed (label notes the
    scale); each is provenance-stamped to the projections section.
    """
    projections: dict[str, list[SourcedValue]] = {}
    block = _section(
        text,
        "Ansys Prospective Financial Information",
        ["Management Case 2"],
    )
    if not block:
        return projections

    def _row(label_pat: str, metric: str, key: str) -> None:
        m = re.search(label_pat + r"\s+((?:\$ ?[0-9,]+ ?)+)", block)
        if not m:
            return
        nums = re.findall(r"\$ ?([0-9,]+)", m.group(1))
        quote = _quote_around(block, m, before=20, after=10)
        prov = _prov(
            "Certain Unaudited Prospective Financial Information — Management Case 1",
            quote,
            ref,
        )
        projections[key] = [
            SourcedValue(
                value=_clean_num(n),
                provenance=prov,
                unit="USD millions",
                label=f"{metric} (Management Case 1, FY{2024 + i}E)",
            )
            for i, n in enumerate(nums)
        ]

    _row(r"Revenue", "Revenue", "revenue")
    _row(r"Unlevered Free Cash Flow ?\(2\)", "Unlevered Free Cash Flow", "unlevered_free_cash_flow")
    return projections
