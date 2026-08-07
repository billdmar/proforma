"""Frozen data contract: the normalized shape of SEC XBRL facts + deal terms.

Shared data contract — edit deliberately; everything builds against it. Every subagent builds against
these types. The ``NormalizedFacts`` half is reused near-verbatim from the thesis project
(cited in docs/DESIGN.md); the merger-specific half (``DealTerms``, ``FairnessDisclosure``,
``DocProvenance`` and friends) is new for proforma. The guiding ideas:

* **One canonical vocabulary.** Companies tag the same economic concept with
  different XBRL tags across filings and eras (e.g. ``Revenues`` vs
  ``RevenueFromContractWithCustomerExcludingAssessedTax``). The normalization
  layer maps every accepted tag to exactly one ``LineItem`` here.
  Downstream engines never see a raw XBRL tag — only ``LineItem``.

* **Provenance is mandatory.** Every value keeps a pointer back to the XBRL
  tag, unit, accession, and form it came from, so the XBRL tie-out gate can
  reconcile each historical statement line to the SEC-reported fact.

* **Restatements resolve to latest.** When multiple accessions report the same
  (LineItem, Period), the fact from the most recent accession wins; superseded
  facts are retained in ``superseded`` for auditability, never silently dropped.

* **Honest unknowns.** A concept the filer did not report is simply absent from
  the facts map. Engines must treat "missing" as missing (None) — never
  fabricate or interpolate a value to fill a gap (see CLAUDE.md rationale).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum


# ---------------------------------------------------------------------------
# Canonical line items — the single vocabulary downstream engines consume.
# ---------------------------------------------------------------------------
class Statement(StrEnum):
    """Which financial statement a line item belongs to."""

    INCOME = "income_statement"
    BALANCE = "balance_sheet"
    CASHFLOW = "cash_flow_statement"


class LineItem(StrEnum):
    """Canonical financial-statement concepts.

    The value is a stable snake_case key used in serialized fixtures and as
    workbook row identifiers. Members are grouped by statement. This list is
    the contract: the EDGAR layer's tag-alias map must resolve to exactly these, and
    the statement builder builds statements from exactly these. Adding a member is an
    maintainer-owned contract change.
    """

    # --- Income statement ---
    REVENUE = "revenue"
    COST_OF_REVENUE = "cost_of_revenue"
    GROSS_PROFIT = "gross_profit"
    SGA = "sga_expense"  # selling, general & administrative
    RND = "rnd_expense"  # research & development
    OTHER_OPERATING_EXPENSE = "other_operating_expense"
    OPERATING_INCOME = "operating_income"  # EBIT
    INTEREST_EXPENSE = "interest_expense"
    INTEREST_INCOME = "interest_income"
    OTHER_NONOPERATING = "other_nonoperating_income"
    PRETAX_INCOME = "pretax_income"
    INCOME_TAX_EXPENSE = "income_tax_expense"
    NET_INCOME = "net_income"
    DEP_AMORT = "depreciation_amortization"  # D&A (often disclosed on CF)
    EPS_BASIC = "eps_basic"
    EPS_DILUTED = "eps_diluted"
    SHARES_BASIC = "weighted_avg_shares_basic"
    SHARES_DILUTED = "weighted_avg_shares_diluted"

    # --- Balance sheet ---
    CASH = "cash_and_equivalents"
    SHORT_TERM_INVESTMENTS = "short_term_investments"
    ACCOUNTS_RECEIVABLE = "accounts_receivable"
    INVENTORY = "inventory"
    OTHER_CURRENT_ASSETS = "other_current_assets"
    TOTAL_CURRENT_ASSETS = "total_current_assets"
    PPE_NET = "property_plant_equipment_net"
    GOODWILL = "goodwill"
    INTANGIBLES = "intangible_assets"
    OPERATING_LEASE_ROU = "operating_lease_right_of_use_asset"
    OTHER_NONCURRENT_ASSETS = "other_noncurrent_assets"
    TOTAL_ASSETS = "total_assets"
    ACCOUNTS_PAYABLE = "accounts_payable"
    ACCRUED_LIABILITIES = "accrued_liabilities"
    SHORT_TERM_DEBT = "short_term_debt"  # incl. current portion of LT debt
    CURRENT_OPERATING_LEASE = "operating_lease_liability_current"
    OTHER_CURRENT_LIABILITIES = "other_current_liabilities"
    TOTAL_CURRENT_LIABILITIES = "total_current_liabilities"
    LONG_TERM_DEBT = "long_term_debt"
    NONCURRENT_OPERATING_LEASE = "operating_lease_liability_noncurrent"
    DEFERRED_TAX_LIABILITIES = "deferred_tax_liabilities"
    OTHER_NONCURRENT_LIABILITIES = "other_noncurrent_liabilities"
    TOTAL_LIABILITIES = "total_liabilities"
    COMMON_STOCK = "common_stock_and_apic"  # par + additional paid-in capital
    RETAINED_EARNINGS = "retained_earnings"
    TREASURY_STOCK = "treasury_stock"
    AOCI = "accumulated_other_comprehensive_income"
    TOTAL_EQUITY = "total_stockholders_equity"
    SHARES_OUTSTANDING = "common_shares_outstanding"  # period-end, for EV bridge

    # --- Cash flow statement ---
    CFO = "cash_from_operations"
    DA_CF = "depreciation_amortization_cf"  # D&A as shown on CF
    STOCK_COMP = "stock_based_compensation"
    CHANGE_IN_WC = "change_in_working_capital"
    CAPEX = "capital_expenditures"
    CFI = "cash_from_investing"
    DIVIDENDS_PAID = "dividends_paid"
    SHARE_REPURCHASES = "share_repurchases"
    DEBT_ISSUED = "debt_issued"
    DEBT_REPAID = "debt_repaid"
    CFF = "cash_from_financing"
    FX_EFFECT = "fx_effect_on_cash"
    NET_CHANGE_IN_CASH = "net_change_in_cash"


# Which statement each line item rolls up to (used by tie-out & workbook layout).
STATEMENT_OF: dict[LineItem, Statement] = {
    **dict.fromkeys(
        [
            LineItem.REVENUE,
            LineItem.COST_OF_REVENUE,
            LineItem.GROSS_PROFIT,
            LineItem.SGA,
            LineItem.RND,
            LineItem.OTHER_OPERATING_EXPENSE,
            LineItem.OPERATING_INCOME,
            LineItem.INTEREST_EXPENSE,
            LineItem.INTEREST_INCOME,
            LineItem.OTHER_NONOPERATING,
            LineItem.PRETAX_INCOME,
            LineItem.INCOME_TAX_EXPENSE,
            LineItem.NET_INCOME,
            LineItem.DEP_AMORT,
            LineItem.EPS_BASIC,
            LineItem.EPS_DILUTED,
            LineItem.SHARES_BASIC,
            LineItem.SHARES_DILUTED,
        ],
        Statement.INCOME,
    ),
    **dict.fromkeys(
        [
            LineItem.CASH,
            LineItem.SHORT_TERM_INVESTMENTS,
            LineItem.ACCOUNTS_RECEIVABLE,
            LineItem.INVENTORY,
            LineItem.OTHER_CURRENT_ASSETS,
            LineItem.TOTAL_CURRENT_ASSETS,
            LineItem.PPE_NET,
            LineItem.GOODWILL,
            LineItem.INTANGIBLES,
            LineItem.OPERATING_LEASE_ROU,
            LineItem.OTHER_NONCURRENT_ASSETS,
            LineItem.TOTAL_ASSETS,
            LineItem.ACCOUNTS_PAYABLE,
            LineItem.ACCRUED_LIABILITIES,
            LineItem.SHORT_TERM_DEBT,
            LineItem.CURRENT_OPERATING_LEASE,
            LineItem.OTHER_CURRENT_LIABILITIES,
            LineItem.TOTAL_CURRENT_LIABILITIES,
            LineItem.LONG_TERM_DEBT,
            LineItem.NONCURRENT_OPERATING_LEASE,
            LineItem.DEFERRED_TAX_LIABILITIES,
            LineItem.OTHER_NONCURRENT_LIABILITIES,
            LineItem.TOTAL_LIABILITIES,
            LineItem.COMMON_STOCK,
            LineItem.RETAINED_EARNINGS,
            LineItem.TREASURY_STOCK,
            LineItem.AOCI,
            LineItem.TOTAL_EQUITY,
            LineItem.SHARES_OUTSTANDING,
        ],
        Statement.BALANCE,
    ),
    **dict.fromkeys(
        [
            LineItem.CFO,
            LineItem.DA_CF,
            LineItem.STOCK_COMP,
            LineItem.CHANGE_IN_WC,
            LineItem.CAPEX,
            LineItem.CFI,
            LineItem.DIVIDENDS_PAID,
            LineItem.SHARE_REPURCHASES,
            LineItem.DEBT_ISSUED,
            LineItem.DEBT_REPAID,
            LineItem.CFF,
            LineItem.FX_EFFECT,
            LineItem.NET_CHANGE_IN_CASH,
        ],
        Statement.CASHFLOW,
    ),
}


# ---------------------------------------------------------------------------
# Periods & units
# ---------------------------------------------------------------------------
class PeriodType(StrEnum):
    """XBRL contexts are either a point-in-time (instant) or a span (duration)."""

    INSTANT = "instant"  # balance-sheet items: value AT end date
    DURATION = "duration"  # income/cash-flow items: value OVER [start, end]


class Unit(StrEnum):
    """Reporting unit for a fact. Normalization stores raw magnitudes (USD, not
    thousands/millions); the workbook applies display scaling."""

    USD = "USD"
    SHARES = "shares"
    USD_PER_SHARE = "USD/shares"
    PURE = "pure"  # ratios, counts (e.g. store counts if ever tagged)


@dataclass(frozen=True)
class Period:
    """A fiscal period. For INSTANT, ``start`` is None and ``end`` is the date.

    ``fy`` is the fiscal year and ``fp`` the fiscal period ("FY", "Q1".."Q4").
    Two periods are equal iff their (type, start, end) match — fy/fp are labels.
    """

    ptype: PeriodType
    end: date
    start: date | None = None
    fy: int | None = None
    fp: str | None = None

    def __post_init__(self) -> None:
        if self.ptype is PeriodType.DURATION and self.start is None:
            raise ValueError("DURATION period requires a start date")
        if self.ptype is PeriodType.INSTANT and self.start is not None:
            raise ValueError("INSTANT period must not have a start date")

    @property
    def key(self) -> tuple:
        """Identity used for de-duplication and dict keys."""
        return (self.ptype.value, self.start, self.end)


@dataclass(frozen=True)
class Provenance:
    """Where a normalized value came from, for the XBRL tie-out gate."""

    xbrl_tag: str  # the raw us-gaap/dei tag actually used
    taxonomy: str  # "us-gaap", "dei", etc.
    unit: Unit
    accession: str  # SEC accession no. (e.g. "0000910521-24-000012")
    form: str  # "10-K", "10-Q"
    filed: date  # filing date (for latest-accession resolution)
    frame: str | None = None  # XBRL frame if sourced via the frames API


@dataclass(frozen=True)
class Fact:
    """A single normalized datapoint: one LineItem, one Period, one value."""

    line_item: LineItem
    period: Period
    value: float
    provenance: Provenance
    # Facts from older accessions that were superseded by this one (restatements).
    superseded: tuple[Provenance, ...] = ()

    @property
    def key(self) -> tuple:
        return (self.line_item.value, self.period.key)


@dataclass
class CompanyMeta:
    """Identity of the filer."""

    cik: str  # zero-padded 10-digit CIK, e.g. "0000910521"
    ticker: str  # e.g. "DECK"
    name: str  # e.g. "Deckers Outdoor Corp"
    fiscal_year_end: str | None = None  # "MM-DD", e.g. "03-31"
    sic: str | None = None  # standard industrial classification code


@dataclass
class NormalizedFacts:
    """The output of the EDGAR layer and the input to every engine.

    ``facts`` is keyed by (LineItem, Period.key) -> Fact so lookups are O(1).
    Helper accessors keep engines from touching the raw dict shape.
    """

    company: CompanyMeta
    facts: dict[tuple, Fact] = field(default_factory=dict)

    def add(self, fact: Fact) -> None:
        """Insert a fact, resolving restatements to the latest accession.

        If a fact for the same (LineItem, Period) already exists, the one with
        the later filing date wins; the loser is recorded under ``superseded``.
        """
        existing = self.facts.get(fact.key)
        if existing is None:
            self.facts[fact.key] = fact
            return
        newer, older = (
            (fact, existing)
            if fact.provenance.filed >= existing.provenance.filed
            else (existing, fact)
        )
        merged_superseded = newer.superseded + older.superseded + (older.provenance,)
        self.facts[fact.key] = Fact(
            line_item=newer.line_item,
            period=newer.period,
            value=newer.value,
            provenance=newer.provenance,
            superseded=merged_superseded,
        )

    def get(self, line_item: LineItem, period: Period) -> Fact | None:
        return self.facts.get((line_item.value, period.key))

    def value(self, line_item: LineItem, period: Period) -> float | None:
        """Value or None. Honest-unknown contract: missing means missing."""
        f = self.facts.get((line_item.value, period.key))
        return f.value if f is not None else None

    def annual_periods(self) -> list[Period]:
        """Fiscal-year DURATION periods, sorted ascending by end date."""
        seen: dict[tuple, Period] = {}
        for f in self.facts.values():
            p = f.period
            if p.ptype is PeriodType.DURATION and p.fp == "FY":
                seen[p.key] = p
        return sorted(seen.values(), key=lambda p: p.end)

    def instant_periods(self) -> list[Period]:
        """Balance-sheet INSTANT periods (period-ends), sorted ascending."""
        seen: dict[tuple, Period] = {}
        for f in self.facts.values():
            if f.period.ptype is PeriodType.INSTANT:
                seen[f.period.key] = f.period
        return sorted(seen.values(), key=lambda p: p.end)


# ===========================================================================
# Merger-specific contracts (proforma-only; frozen at W0, ORCH-owned).
#
# The XBRL-level ``Provenance`` above stamps facts pulled from the structured
# CompanyFacts API. Deal facts, advisor analyses, management projections, and
# synergy figures instead come from the *text* of the merger proxy (DEFM14A /
# S-4) and the deal 8-Ks. Those get ``DocProvenance``: accession + form + a
# human-locatable section reference and the quoted snippet, so every disclosed
# figure is auditable back to the filing (CLAUDE.md: "no unsourced deal facts").
# ===========================================================================
class ConsiderationType(StrEnum):
    """How a deal's per-share consideration is paid."""

    CASH = "cash"
    STOCK = "stock"
    MIXED = "cash_and_stock"


@dataclass(frozen=True)
class DocProvenance:
    """Where a text-extracted deal fact came from, for the deal-fact audit.

    Distinct from XBRL ``Provenance``: the source is a filing *document*, not a
    tagged fact. ``section`` is a human-locatable pointer (e.g.
    "Opinion of Financial Advisor — Discounted Cash Flow Analysis") and
    ``quote`` is the verbatim snippet the figure was read from.
    """

    accession: str  # SEC accession no. (e.g. "0001013462-24-000123")
    form: str  # "DEFM14A", "S-4", "8-K", "425"
    filed: date
    section: str  # human-locatable section/heading within the filing
    quote: str = ""  # verbatim snippet supporting the extracted figure
    url: str | None = None  # canonical Archives document URL, if built
    page: int | None = None  # page/exhibit number when applicable


@dataclass(frozen=True)
class SourcedValue:
    """A single scalar with its document provenance. Used pervasively in the
    deal/fairness records so *every* extracted number carries its source.

    ``value`` may be None for an honest unknown (a figure the filing does not
    disclose); the provenance still records where we looked."""

    value: float | None
    provenance: DocProvenance
    unit: str = "USD"  # "USD", "USD/share", "shares", "ratio", "percent"
    label: str = ""  # what the number is, in words


@dataclass(frozen=True)
class SourcedRange:
    """A disclosed low–high range (e.g. an advisor's implied per-share range)
    with provenance. ``low``/``high`` may be None for honest unknowns."""

    low: float | None
    high: float | None
    provenance: DocProvenance
    unit: str = "USD/share"
    label: str = ""


@dataclass
class DealTerms:
    """The transaction as disclosed — every field provenance-stamped.

    Populated by the EDGAR extraction layer from the merger agreement / proxy /
    8-Ks. This is disclosed FACT (not our assumption); our own modeling choices
    live in ProjectionAssumptions / DealAssumptions and docs/ASSUMPTIONS.md.
    """

    acquirer_ticker: str
    target_ticker: str
    acquirer_name: str
    target_name: str
    announce_date: date
    close_date: date | None  # None while pending
    consideration_type: ConsiderationType
    # Per-target-share consideration. Any leg absent for a given deal is None.
    cash_per_share: SourcedValue | None = None
    exchange_ratio: SourcedValue | None = None  # acquirer shares per target share
    stated_price_per_share: SourcedValue | None = None  # headline deal price/sh
    reference_acquirer_price: SourcedValue | None = None  # for valuing the stock leg
    # Premium as disclosed (basis noted in the label/section, e.g. "unaffected").
    premium_pct: SourcedValue | None = None
    premium_reference_price: SourcedValue | None = None
    # Financing & fees as disclosed.
    new_debt: SourcedValue | None = None
    cash_on_hand_used: SourcedValue | None = None
    advisory_financing_fees: SourcedValue | None = None
    # Management-disclosed synergies (a DISCLOSED assumption, quoted & sourced).
    disclosed_synergies_annual: SourcedValue | None = None
    synergy_phasein_note: DocProvenance | None = None
    # Target shares outstanding used to gross up to aggregate consideration.
    target_shares_outstanding: SourcedValue | None = None
    notes: str = ""


@dataclass(frozen=True)
class AdvisorMethodology:
    """One valuation methodology disclosed in a fairness opinion, with the
    advisor's disclosed assumption ranges and the implied per-share range it
    produced. This is the raw material for the fairness DIFFERENTIAL: we run the
    disclosed assumptions through OUR engine and check our implied range
    reproduces ``implied_range``."""

    method: str  # "DCF" | "Selected Public Companies" | "Selected Precedent Transactions" | "Premiums Paid" | ...
    implied_range: SourcedRange  # the advisor's disclosed implied per-share range
    # Disclosed assumption ranges keyed by name (e.g. "discount_rate",
    # "perpetuity_growth", "ev_ebitda_multiple"), each a sourced low–high range.
    assumptions: dict[str, SourcedRange] = field(default_factory=dict)
    notes: str = ""


@dataclass
class FairnessDisclosure:
    """A financial advisor's disclosed fairness analyses for one side of the
    deal, extracted from the proxy — every figure provenance-stamped."""

    advisor: str  # e.g. "Qatalyst Partners", "Evercore"
    represents: str  # ticker of the party the advisor represents
    methodologies: list[AdvisorMethodology] = field(default_factory=list)
    # Management projections disclosed in the proxy (the "Certain Financial
    # Projections" section), keyed by metric -> per-year sourced values.
    management_projections: dict[str, list[SourcedValue]] = field(default_factory=dict)
    offered_consideration: SourcedValue | None = None  # price the range is compared to
    notes: str = ""
