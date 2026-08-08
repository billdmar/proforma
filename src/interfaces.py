"""Frozen engine-interface contract.

Shared data contract — edit deliberately; everything builds against it. These are the typed boundaries
between the engines each subagent owns. They exist so W1 can fan out in
parallel: every subagent codes to these signatures and dataclasses without
waiting on another's implementation. Where a shape is an input to one engine
and an output of another, it lives here so there is one definition.

The single-company halves (statement builder, DCF, comps, LBO) are reused from
the thesis project and reappear here because the fairness differential runs the
advisors' disclosed assumptions through the same DCF/comps/precedents engines.
The merger halves (deal engine, combination engine, MergerModelBundle) are new.

Signs & conventions (contract — enforced by the audit + invariant gates):
* Values are in raw USD magnitudes (not thousands/millions). The workbook
  applies display scaling; the engine never pre-scales.
* Cash *outflows* on the cash-flow statement are negative (capex, dividends,
  repurchases, debt repaid). Inflows are positive.
* Interest expense is stored positive; the model subtracts it explicitly.
* Shares are share counts, not millions of shares.
* Deal math: goodwill = equity purchase price − net identifiable assets
  acquired (incl. any asset step-ups net of the deferred-tax liability they
  create). Sources MUST equal uses. Pro forma EPS = pro forma net income /
  pro forma diluted shares; accretion/(dilution) = pro forma EPS / acquirer
  standalone EPS − 1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from src.schema import (
    CompanyMeta,
    DealTerms,
    FairnessDisclosure,
    LineItem,
    NormalizedFacts,
    Period,
)


# ===========================================================================
# Assumptions — the blue inputs. Set for the flagship model (the judgment core).
# ===========================================================================
@dataclass
class ProjectionAssumptions:
    """Drivers for the 5-year 3-statement projection.

    Every field is a per-projection-year sequence unless noted. Lists are
    length ``n_years``. Rationale for each flagship value lives in
    docs/ASSUMPTIONS.md (2-4 lines, sourced) — never hard-coded silently.
    """

    n_years: int = 5
    # Revenue: either explicit growth rates or a driver build handed in already.
    revenue_growth: list[float] = field(default_factory=list)  # e.g. [0.12, 0.10, ...]
    # Margins (as % of revenue) unless the name says otherwise.
    gross_margin: list[float] = field(default_factory=list)
    sga_pct_revenue: list[float] = field(default_factory=list)
    rnd_pct_revenue: list[float] = field(default_factory=list)
    # Working-capital drivers (days).
    dso: list[float] = field(default_factory=list)  # days sales outstanding
    dio: list[float] = field(default_factory=list)  # days inventory outstanding
    dpo: list[float] = field(default_factory=list)  # days payables outstanding
    # Capex & D&A.
    capex_pct_revenue: list[float] = field(default_factory=list)
    da_pct_revenue: list[float] = field(default_factory=list)
    # Tax & financing.
    tax_rate: list[float] = field(default_factory=list)
    interest_rate_on_debt: float = 0.0  # avg rate applied to average debt balance
    interest_rate_on_cash: float = 0.0  # yield on cash & ST investments
    min_cash: float = 0.0  # revolver plug maintains at least this cash balance
    dividend_payout: list[float] = field(default_factory=list)  # % of net income


@dataclass
class WACCInputs:
    """CAPM + capital-structure inputs for the discount rate."""

    risk_free_rate: float  # 10Y UST, sourced
    beta: float  # levered beta, with source note in ASSUMPTIONS.md
    equity_risk_premium: float
    pretax_cost_of_debt: float  # from filings (interest expense / avg debt) or rating
    tax_rate: float
    # Capital structure weights use MARKET value of equity, BOOK value of debt.
    market_cap: float
    total_debt: float


@dataclass
class TerminalAssumptions:
    """Terminal-value inputs. Both methods computed; report weights them."""

    method: str = "both"  # "gordon" | "exit_multiple" | "both"
    terminal_growth: float = 0.0  # Gordon g; contract: MUST be < WACC (sanity gate)
    exit_ev_ebitda: float = 0.0  # exit multiple on terminal-year EBITDA
    mid_year_convention: bool = True


# ===========================================================================
# Statement model — output of the statement builder, input to valuation/workbook.
# ===========================================================================
@dataclass
class StatementSet:
    """Historical + projected statements in one object.

    ``periods`` is the ordered list of column headers (historical then
    projected). ``rows`` maps each LineItem to a value-per-period list aligned
    to ``periods``; None entries are honest unknowns. ``n_hist`` marks the
    boundary: periods[:n_hist] are historical (tie out to XBRL), periods[n_hist:]
    are projected (driven by assumptions).
    """

    periods: list[Period]
    rows: dict[LineItem, list[float | None]]
    n_hist: int

    def series(self, li: LineItem) -> list[float | None]:
        return self.rows.get(li, [None] * len(self.periods))


class StatementBuilder(Protocol):
    """the statement builder. Builds historicals from facts, then projects forward."""

    def build_historical(self, facts: NormalizedFacts) -> StatementSet: ...

    def project(self, hist: StatementSet, assumptions: ProjectionAssumptions) -> StatementSet: ...


# ===========================================================================
# Valuation — the valuation engine.
# ===========================================================================
@dataclass
class DCFResult:
    wacc: float
    pv_explicit_fcff: float
    terminal_value_gordon: float
    terminal_value_exit: float
    pv_terminal_gordon: float
    pv_terminal_exit: float
    enterprise_value_gordon: float
    enterprise_value_exit: float
    # EV -> equity bridge
    net_debt: float
    minority_interest: float
    equity_value_gordon: float
    equity_value_exit: float
    shares_diluted: float
    implied_price_gordon: float
    implied_price_exit: float
    fcff_by_year: list[float] = field(default_factory=list)
    discount_factors: list[float] = field(default_factory=list)
    # Normalized steady-state terminal FCFF fed to the Gordon perpetuity (capex
    # set equal to D&A so PP&E doesn't shrink forever). Defaults 0.0 for
    # backward compatibility with hand-built fixtures.
    terminal_fcff_normalized: float = 0.0
    # Full-year discount factor (1+WACC)^-N used for the exit-multiple terminal
    # value (a year-end sale), distinct from the mid-year explicit-period factors.
    discount_factor_exit: float = 0.0


class ValuationEngine(Protocol):
    """the valuation engine. WACC + FCFF DCF with both terminal methods."""

    def wacc(self, inputs: WACCInputs) -> float: ...

    def dcf(
        self,
        statements: StatementSet,
        wacc_inputs: WACCInputs,
        terminal: TerminalAssumptions,
    ) -> DCFResult: ...


# ===========================================================================
# Comps & precedents — the comps engine.
# ===========================================================================
@dataclass
class PeerMultiples:
    ticker: str
    name: str
    enterprise_value: float
    equity_value: float
    ev_revenue_ltm: float | None
    ev_ebitda_ltm: float | None
    pe_ltm: float | None
    ev_revenue_ntm: float | None = None
    ev_ebitda_ntm: float | None = None


@dataclass
class CompsResult:
    peers: list[PeerMultiples]
    # Summary stats across the peer set, per multiple.
    stats: dict[str, dict[str, float]]  # e.g. {"ev_ebitda_ltm": {"median":..,"mean":..}}
    # Implied value for the subject from applying peer medians to its metrics.
    implied_ev_from_ebitda: float | None = None
    implied_price_from_ebitda: float | None = None
    implied_price_from_revenue: float | None = None
    implied_price_from_pe: float | None = None


@dataclass
class PrecedentTransaction:
    date: str
    acquirer: str
    target: str
    ev: float
    ev_revenue: float | None
    ev_ebitda: float | None
    source: str  # citation — every precedent row is sourced


class CompsEngine(Protocol):
    """the comps engine."""

    def build_peer_multiples(
        self, subject: NormalizedFacts, peers: list[NormalizedFacts]
    ) -> CompsResult: ...

    def load_precedents(self, csv_path: str) -> list[PrecedentTransaction]: ...


# ===========================================================================
# LBO — the LBO engine .
# ===========================================================================
@dataclass
class LBOAssumptions:
    entry_premium: float  # premium over current price
    entry_ev_ebitda: float | None  # if None, derived from entry equity + net debt
    debt_pct_of_ev: float  # leverage at entry
    debt_rate: float
    cash_sweep_pct: float  # % of FCF sweeping to debt paydown
    exit_ev_ebitda: float
    hold_years: int = 5


@dataclass
class LBOResult:
    sources: dict[str, float]
    uses: dict[str, float]
    debt_schedule: list[dict[str, float]]  # per-year: begin, interest, sweep, end
    exit_equity_value: float
    irr: float
    moic: float

    def sources_equal_uses(self, tol: float = 0.01) -> bool:
        return abs(sum(self.sources.values()) - sum(self.uses.values())) <= tol


class LBOEngine(Protocol):
    """the LBO engine."""

    def run(
        self, statements: StatementSet, assumptions: LBOAssumptions, current_price: float
    ) -> LBOResult: ...


# ===========================================================================
# Workbook writer — the workbook writer. Emits LIVE formulas, never baked values.
# ===========================================================================
class WorkbookWriter(Protocol):
    """the workbook writer. Writes the .xlsx per docs/WORKBOOK_SPEC.md."""

    def write(self, path: str, model: MergerModelBundle) -> None: ...


# ===========================================================================
# Verification — the verifier . The moat.
# ===========================================================================
@dataclass
class CellDiff:
    sheet: str
    cell: str
    engine_value: float | None
    workbook_value: float | None
    ok: bool


@dataclass
class DifferentialReport:
    cells_checked: int
    mismatches: list[CellDiff]

    @property
    def passed(self) -> bool:
        return len(self.mismatches) == 0


class Verifier(Protocol):
    """the verifier. Recalculates the workbook and diffs it against the engine."""

    def recalc_and_diff(
        self, workbook_path: str, model: MergerModelBundle, tol: float = 0.01
    ) -> DifferentialReport: ...


# ===========================================================================
# DEAL ENGINE — src/deal. Consideration, sources & uses, purchase price
# accounting. Inputs: DealTerms (disclosed) + DealAssumptions (ours).
# ===========================================================================
@dataclass
class DealAssumptions:
    """OUR modeling choices for the deal (distinct from disclosed DealTerms).

    Every value carries a 2–4 line rationale in docs/ASSUMPTIONS.md. Where a
    value simply mirrors a disclosed term (e.g. cash-per-share), it is set from
    DealTerms, not invented — but the modeling *choices* (fee %, step-up %,
    useful life, financing split) are ours and labeled as such.
    """

    # Financing of the cash consideration + fees.
    new_debt: float = 0.0  # new acquisition debt raised
    new_debt_rate: float = 0.0  # pre-tax coupon on new debt
    cash_on_hand_used: float = 0.0  # acquirer balance-sheet cash applied
    foregone_cash_yield: float = 0.0  # yield lost on the cash used
    # Transaction & financing fees (expensed vs capitalized noted in ASSUMPTIONS).
    advisory_fees: float = 0.0
    financing_fees: float = 0.0
    # Purchase price accounting choices.
    intangible_step_up: float = 0.0  # $ written up to identifiable intangibles
    intangible_useful_life_years: float = 0.0  # for incremental amortization
    ppe_step_up: float = 0.0
    ppe_useful_life_years: float = 0.0
    deferred_tax_rate: float = 0.0  # DTL rate on step-ups (book/tax basis diff)
    target_existing_goodwill_written_off: bool = True
    # Effective tax rate for pro forma adjustments.
    marginal_tax_rate: float = 0.0
    # New shares issued to fund the stock leg (share count); reference price for
    # valuing them is a disclosed term.
    new_shares_issued: float = 0.0


@dataclass
class Consideration:
    """The per-share and aggregate consideration build."""

    cash_per_share: float
    stock_per_share_value: float  # exchange_ratio * reference acquirer price
    total_per_share: float
    target_shares: float
    aggregate_cash: float
    aggregate_stock_value: float
    equity_purchase_price: float  # aggregate consideration to target holders
    implied_premium_pct: float | None = None
    exchange_ratio: float | None = None
    new_shares_issued: float = 0.0


@dataclass
class SourcesAndUses:
    """Sources must equal uses (invariant). Keyed dicts so the workbook and the
    invariant runner iterate the same line set."""

    sources: dict[str, float]  # e.g. {"new_debt":.., "cash_on_hand":.., "stock_issued":..}
    uses: dict[
        str, float
    ]  # e.g. {"equity_purchase_price":.., "refinance_target_debt":.., "fees":..}

    @property
    def total_sources(self) -> float:
        return sum(self.sources.values())

    @property
    def total_uses(self) -> float:
        return sum(self.uses.values())

    def balances(self, tol: float = 0.01) -> bool:
        return abs(self.total_sources - self.total_uses) <= tol


@dataclass
class PurchasePriceAllocation:
    """Equity purchase price → identifiable net assets → step-ups → DTL →
    goodwill. Goodwill is the plug: equity_purchase_price − net_identifiable."""

    equity_purchase_price: float
    target_book_equity: float
    target_existing_goodwill: float  # written off before re-allocation
    identifiable_net_assets_at_book: float  # book equity less existing goodwill
    intangible_step_up: float
    ppe_step_up: float
    deferred_tax_liability: float  # created by the step-ups
    net_identifiable_assets: float  # book net assets + step-ups − DTL
    goodwill: float  # equity_purchase_price − net_identifiable_assets

    def ties(self, tol: float = 0.01) -> bool:
        return (
            abs(self.goodwill - (self.equity_purchase_price - self.net_identifiable_assets)) <= tol
        )


@dataclass
class DealResult:
    """Everything the deal engine computes from DealTerms + DealAssumptions."""

    consideration: Consideration
    sources_and_uses: SourcesAndUses
    ppa: PurchasePriceAllocation
    # Incremental annual D&A from step-ups (amortization of intangibles + extra
    # PP&E depreciation) — feeds the pro forma income statement.
    incremental_da_annual: float = 0.0


class DealEngine(Protocol):
    """the deal engine. Consideration + S&U + purchase price accounting."""

    def build(self, terms: DealTerms, assumptions: DealAssumptions) -> DealResult: ...


# ===========================================================================
# COMBINATION ENGINE — src/combine. Pro forma statements, EPS bridge,
# accretion/dilution, contribution & exchange-ratio analysis.
# ===========================================================================
@dataclass
class SynergyCase:
    """A synergy scenario: annual run-rate phased in over the projection years.

    ``name`` is "Management (disclosed)" or "Our conservative case" etc. — both
    are labeled ASSUMPTIONS. ``phase_in`` is the fraction realized each year
    (length = projection years), summing the ramp to the run-rate."""

    name: str
    run_rate_annual: float  # steady-state pre-tax cost synergies
    phase_in: list[float]  # fraction of run-rate realized per projected year
    is_disclosed: bool = False  # True for management's figure (quoted+sourced)

    def realized(self, year_idx: int) -> float:
        if 0 <= year_idx < len(self.phase_in):
            return self.run_rate_annual * self.phase_in[year_idx]
        return self.run_rate_annual  # steady state beyond the ramp


@dataclass
class EPSBridge:
    """One projected year's walk from standalone to pro forma EPS."""

    year: Period
    acquirer_standalone_ni: float
    target_standalone_ni: float
    # All four adjustment legs are stored AFTER-TAX so the bridge is a pure
    # additive walk to pro forma NI (acq + tgt − int − foregone − D&A + syn) and
    # the workbook mirrors it cell-for-cell. Interest is tax-deductible, so its
    # net-income impact is coupon × (1 − t); likewise the foregone cash yield.
    incremental_interest_aftertax: float  # on new debt, after tax (positive; subtracted)
    foregone_interest_aftertax: float  # on cash used, after tax (positive; subtracted)
    incremental_da_aftertax: float  # step-up amortization, after tax (subtracted)
    synergies_aftertax: float  # realized synergies, after tax (added)
    pro_forma_net_income: float
    acquirer_standalone_shares: float
    new_shares_issued: float
    pro_forma_shares: float
    acquirer_standalone_eps: float
    pro_forma_eps: float

    @property
    def accretion_dilution_pct(self) -> float | None:
        if self.acquirer_standalone_eps in (0.0, None):
            return None
        return self.pro_forma_eps / self.acquirer_standalone_eps - 1.0


@dataclass
class ContributionAnalysis:
    """Each party's contribution to combined revenue / EBITDA / net income vs.
    its pro forma ownership of the combined entity."""

    acquirer_revenue: float
    target_revenue: float
    acquirer_ebitda: float
    target_ebitda: float
    acquirer_net_income: float
    target_net_income: float
    acquirer_ownership_pct: float  # existing acquirer shares / pro forma shares
    target_ownership_pct: float  # new shares issued / pro forma shares


@dataclass
class CombinationResult:
    """Pro forma output for one synergy case across the projection horizon."""

    synergy_case: SynergyCase
    proforma_statements: StatementSet  # combined IS/BS by projected year
    eps_bridge: list[EPSBridge]  # one per projected year
    contribution: ContributionAnalysis

    def accretion_by_year(self) -> list[float | None]:
        return [b.accretion_dilution_pct for b in self.eps_bridge]


class CombinationEngine(Protocol):
    """the combination engine. Assembles pro forma statements + A/D."""

    def combine(
        self,
        acquirer: StatementSet,
        target: StatementSet,
        deal: DealResult,
        deal_assumptions: DealAssumptions,
        synergies: SynergyCase,
    ) -> CombinationResult: ...


# ===========================================================================
# SENSITIVITIES — src/scenarios. Premium×synergies + consideration-mix grids,
# breakeven synergies. Monotonicity is a gate (DoD #5).
# ===========================================================================
@dataclass
class SensitivityGrid:
    """A 2-D accretion/(dilution) grid for a single projected year.

    ``row_label``/``col_label`` name the axes (e.g. "premium", "synergies");
    ``values[i][j]`` is Year-``year_idx`` accretion/(dilution) % at
    ``row_values[i]`` × ``col_values[j]``."""

    year_idx: int
    row_label: str
    col_label: str
    row_values: list[float]
    col_values: list[float]
    values: list[list[float | None]]


@dataclass
class SensitivitySet:
    premium_x_synergies: SensitivityGrid
    consideration_mix: SensitivityGrid
    breakeven_synergies: float | None  # run-rate synergies for Year-1 A/D = 0
    breakeven_year_idx: int = 0


# ===========================================================================
# FAIRNESS DIFFERENTIAL — src/fairness. Run the advisors' DISCLOSED assumption
# ranges through OUR engine; compare our implied ranges to their disclosed ones.
# ===========================================================================
@dataclass
class MethodologyReproduction:
    """Our reproduction of one advisor methodology's implied range."""

    advisor: str
    method: str
    disclosed_low: float | None
    disclosed_high: float | None
    our_low: float | None
    our_high: float | None
    overlap_pct: float | None  # |intersection| / |disclosed range|
    deviation_note: str = ""  # investigated in writing, never tuned away


@dataclass
class FairnessDifferentialReport:
    reproductions: list[MethodologyReproduction]

    @property
    def mean_overlap(self) -> float | None:
        vals = [r.overlap_pct for r in self.reproductions if r.overlap_pct is not None]
        return sum(vals) / len(vals) if vals else None


# ===========================================================================
# THE BUNDLE passed to the workbook writer, report renderer, and verifier.
# Single source of truth: the workbook expresses these as formulas, the memo
# renders them, the verifier diffs against them. Nothing here is hand-typed.
# ===========================================================================
@dataclass
class MergerModelBundle:
    """Everything the merger deliverables need, computed by the engines."""

    # Identities & disclosed facts.
    acquirer: CompanyMeta
    target: CompanyMeta
    terms: DealTerms

    # Standalone models (both companies): historicals + driver-based projection.
    acquirer_statements: StatementSet
    target_statements: StatementSet
    acquirer_assumptions: ProjectionAssumptions
    target_assumptions: ProjectionAssumptions

    # Deal structure.
    deal_assumptions: DealAssumptions
    deal: DealResult

    # Combination — one result per synergy case (management + our conservative).
    combinations: list[CombinationResult]

    # Sensitivities.
    sensitivities: SensitivitySet | None = None

    # Precedent transactions (premiums-paid table, curated + cited).
    precedents: list[PrecedentTransaction] = field(default_factory=list)

    # Fairness differential (populated at W2/G2).
    fairness_disclosures: list[FairnessDisclosure] = field(default_factory=list)
    fairness_differential: FairnessDifferentialReport | None = None

    # Standalone target (ANSYS) DCF — our own valuation, framed in the memo's
    # target-valuation section against the offered per-share consideration.
    # Distinct from the fairness differential (which reproduces the ADVISOR's
    # disclosed assumptions); this is OUR standalone view. Populated at W3.
    target_dcf: DCFResult | None = None

    def primary_combination(self) -> CombinationResult:
        """The management-synergy (disclosed) case if present, else the first."""
        for c in self.combinations:
            if c.synergy_case.is_disclosed:
                return c
        return self.combinations[0]
