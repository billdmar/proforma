"""Sensitivity / scenario engine — premium×synergies and consideration-mix
grids plus breakeven synergies for the merger model.

The mechanism is the ``dataclasses.replace`` fan-out: perturb ONE disclosed
assumption, re-fund the deal under a single consistent funding rule, re-run the
deal + combination engine chain, and read Year-``year_idx`` accretion/(dilution)
from the resulting :class:`~src.interfaces.EPSBridge`.

Funding rule (the ONE clean lever — identical for both grids)
-------------------------------------------------------------
Every scenario is a choice of per-share cash + stock consideration. We fund it
so the base structure reproduces the flagship deal exactly, then let the lever
flow through mechanically:

* **Cash consideration** (``cash_per_share × target_shares``) is funded first by
  the acquirer's balance-sheet cash-on-hand, capped at the base-deal level, and
  the remainder by **new acquisition debt** at the base coupon. So
  ``cash_needs = aggregate_cash + fees``,
  ``cash_on_hand_used = min(base_cash_on_hand, cash_needs)``,
  ``new_debt = cash_needs − cash_on_hand_used``.
  At the base structure this yields the flagship's exact $14.3B new debt (the
  flagship was built so sources = uses), so the grids are consistent with the
  base model and never fund with a negative/plug balance.
* **Stock consideration** issues acquirer shares:
  ``new_shares = exchange_ratio × target_shares``, valued at the fixed disclosed
  reference acquirer price. Fees stay at their base level.

Why this makes A/D monotone (the DoD gate):

* **Premium axis** — we scale ``cash_per_share`` (stock leg held fixed) so the
  implied premium hits the target. Higher premium ⇒ more cash ⇒ more new debt ⇒
  more after-tax interest ⇒ lower pro forma NI ⇒ **more dilutive**. The share
  count is unchanged (exchange ratio fixed), so the premium axis is a clean
  interest-cost lever with no share-count confound.
* **Synergy axis** — higher run-rate ⇒ more after-tax synergies added to pro
  forma NI ⇒ **more accretive**. A/D is linear in synergies, so breakeven is a
  clean bisection.

Grids and breakeven assume synergies are **fully realized** at the stated
run-rate (phase-in = 1.0 every year). This removes the phase-in ramp as a
confound so the synergy axis is exactly the annual run-rate and the breakeven
figure reads as "the fully-realized annual run-rate that zeroes Year-N A/D".
"""

from __future__ import annotations

from dataclasses import replace

from src.combine import CombinationEngine
from src.deal import DealEngineImpl
from src.interfaces import (
    CombinationEngine as CombinationEngineProto,
)
from src.interfaces import (
    DealAssumptions,
    MergerModelBundle,
    SensitivityGrid,
    SensitivitySet,
    StatementSet,
    SynergyCase,
)
from src.interfaces import (
    DealEngine as DealEngineProto,
)
from src.schema import DealTerms, LineItem

# --- Default axes -----------------------------------------------------------
# Premiums span the ~28.7% disclosed SNPS/ANSS premium. Synergy run-rates are
# sized to bracket the (large) breakeven of this heavily Year-1-dilutive deal.
DEFAULT_PREMIUMS: list[float] = [0.10, 0.20, 0.30, 0.40, 0.50]
DEFAULT_SYNERGY_RUN_RATES: list[float] = [
    0.0,
    2_000_000_000.0,
    4_000_000_000.0,
    6_000_000_000.0,
    8_000_000_000.0,
]
# Consideration-mix axis: fraction of total per-share value paid in cash.
DEFAULT_CASH_FRACTIONS: list[float] = [0.0, 0.25, 0.50, 0.75, 1.0]

# Bisection cap for breakeven synergies (annual run-rate, USD). Generous enough
# to bracket the root for a deeply dilutive deal; None returned if unattainable.
_BREAKEVEN_CAP = 40_000_000_000.0


def _require(sv, name: str):
    """Return a disclosed SourcedValue, or raise if the leg the grids need is
    absent (the grids re-scale it, so it must exist to be perturbed)."""
    if sv is None or sv.value is None:
        raise ValueError(f"DealTerms.{name} is required to build sensitivities but is absent")
    return sv


def _n_proj(acquirer: StatementSet) -> int:
    return len(acquirer.periods) - acquirer.n_hist


def _accretion_dilution(
    terms: DealTerms,
    base_deal_assumptions: DealAssumptions,
    acquirer: StatementSet,
    target: StatementSet,
    *,
    cash_per_share: float,
    exchange_ratio: float,
    synergy_run_rate: float,
    year_idx: int,
    deal_engine: DealEngineProto,
    combine_engine: CombinationEngineProto,
    target_book_equity: float,
    target_existing_goodwill: float,
) -> float | None:
    """One fan-out evaluation: rebuild the deal at ``(cash_per_share,
    exchange_ratio)`` under the funding rule, run the combination with a fully
    realized ``synergy_run_rate``, and read Year-``year_idx`` A/D."""
    cash_sv = _require(terms.cash_per_share, "cash_per_share")
    xratio_sv = _require(terms.exchange_ratio, "exchange_ratio")
    tgt_shares = _require(terms.target_shares_outstanding, "target_shares_outstanding").value

    new_terms = replace(
        terms,
        cash_per_share=replace(cash_sv, value=cash_per_share),
        exchange_ratio=replace(xratio_sv, value=exchange_ratio),
    )

    aggregate_cash = cash_per_share * tgt_shares
    fees = base_deal_assumptions.advisory_fees + base_deal_assumptions.financing_fees
    cash_needs = aggregate_cash + fees
    cash_on_hand_used = min(base_deal_assumptions.cash_on_hand_used, cash_needs)
    new_debt = cash_needs - cash_on_hand_used

    # The stock-leg share count is derived inside the deal engine from
    # exchange_ratio × target_shares; we only perturb financing here.
    new_da = replace(
        base_deal_assumptions,
        new_debt=new_debt,
        cash_on_hand_used=cash_on_hand_used,
    )
    deal = deal_engine.build(
        new_terms,
        new_da,
        target_book_equity=target_book_equity,
        target_existing_goodwill=target_existing_goodwill,
        refinanced_target_debt=0.0,
    )
    synergies = SynergyCase(
        name="scenario",
        run_rate_annual=synergy_run_rate,
        phase_in=[1.0] * _n_proj(acquirer),
        is_disclosed=False,
    )
    combo = combine_engine.combine(acquirer, target, deal, new_da, synergies)
    return combo.eps_bridge[year_idx].accretion_dilution_pct


def premium_x_synergies_grid(
    terms: DealTerms,
    base_deal_assumptions: DealAssumptions,
    acquirer: StatementSet,
    target: StatementSet,
    *,
    year_idx: int = 0,
    premiums: list[float] | None = None,
    synergy_run_rates: list[float] | None = None,
    deal_engine: DealEngineProto | None = None,
    combine_engine: CombinationEngineProto | None = None,
    target_book_equity: float = 0.0,
    target_existing_goodwill: float = 0.0,
) -> SensitivityGrid:
    """Premium × synergy-run-rate accretion/(dilution) grid for one year.

    Lever: ``cash_per_share`` is scaled so the implied premium over the disclosed
    reference price hits each ``premiums[i]``; the stock leg (exchange ratio) is
    held at the disclosed value. Higher premium ⇒ debt-funded extra cash ⇒ more
    interest ⇒ more dilutive; higher synergies ⇒ more accretive. The grid is
    therefore monotone: non-increasing down each premium column, non-decreasing
    across each synergy row (a DoD gate)."""
    premiums = DEFAULT_PREMIUMS if premiums is None else premiums
    synergy_run_rates = (
        DEFAULT_SYNERGY_RUN_RATES if synergy_run_rates is None else synergy_run_rates
    )
    deal_engine = deal_engine or DealEngineImpl()
    combine_engine = combine_engine or CombinationEngine()

    ref_price = _require(terms.reference_acquirer_price, "reference_acquirer_price").value
    prem_ref = _require(terms.premium_reference_price, "premium_reference_price").value
    xratio = _require(terms.exchange_ratio, "exchange_ratio").value
    stock_per_share_value = xratio * ref_price

    values: list[list[float | None]] = []
    for premium in premiums:
        total_per_share = prem_ref * (1.0 + premium)
        cash_per_share = total_per_share - stock_per_share_value
        row: list[float | None] = []
        for run_rate in synergy_run_rates:
            row.append(
                _accretion_dilution(
                    terms,
                    base_deal_assumptions,
                    acquirer,
                    target,
                    cash_per_share=cash_per_share,
                    exchange_ratio=xratio,
                    synergy_run_rate=run_rate,
                    year_idx=year_idx,
                    deal_engine=deal_engine,
                    combine_engine=combine_engine,
                    target_book_equity=target_book_equity,
                    target_existing_goodwill=target_existing_goodwill,
                )
            )
        values.append(row)

    return SensitivityGrid(
        year_idx=year_idx,
        row_label="premium",
        col_label="synergies",
        row_values=list(premiums),
        col_values=list(synergy_run_rates),
        values=values,
    )


def consideration_mix_grid(
    terms: DealTerms,
    base_deal_assumptions: DealAssumptions,
    acquirer: StatementSet,
    target: StatementSet,
    *,
    year_idx: int = 0,
    cash_fractions: list[float] | None = None,
    synergy_run_rates: list[float] | None = None,
    deal_engine: DealEngineProto | None = None,
    combine_engine: CombinationEngineProto | None = None,
    target_book_equity: float = 0.0,
    target_existing_goodwill: float = 0.0,
) -> SensitivityGrid:
    """Consideration-mix × synergy grid, holding TOTAL per-share value fixed.

    For each cash fraction ``f`` the total base per-share consideration is split
    ``cash_per_share = f × total`` and ``stock_per_share_value = (1−f) × total``;
    the exchange ratio is backed out at the fixed reference price
    (``exchange_ratio = stock_per_share_value / reference_price``). Under the
    funding rule more cash ⇒ more new debt (more after-tax interest, dilutive)
    while fewer shares are issued (accretive). For this deal — an expensive
    target (low earnings yield) funded with ~5% pre-tax debt — the interest cost
    dominates, so **more cash is MORE dilutive**: the grid is non-increasing
    down each cash-fraction column and non-decreasing across each synergy row.
    (The test asserts this measured direction.)"""
    cash_fractions = DEFAULT_CASH_FRACTIONS if cash_fractions is None else cash_fractions
    synergy_run_rates = (
        DEFAULT_SYNERGY_RUN_RATES if synergy_run_rates is None else synergy_run_rates
    )
    deal_engine = deal_engine or DealEngineImpl()
    combine_engine = combine_engine or CombinationEngine()

    ref_price = _require(terms.reference_acquirer_price, "reference_acquirer_price").value
    cash_base = _require(terms.cash_per_share, "cash_per_share").value
    xratio_base = _require(terms.exchange_ratio, "exchange_ratio").value
    total_per_share = cash_base + xratio_base * ref_price

    values: list[list[float | None]] = []
    for frac in cash_fractions:
        cash_per_share = frac * total_per_share
        stock_per_share_value = (1.0 - frac) * total_per_share
        exchange_ratio = stock_per_share_value / ref_price
        row: list[float | None] = []
        for run_rate in synergy_run_rates:
            row.append(
                _accretion_dilution(
                    terms,
                    base_deal_assumptions,
                    acquirer,
                    target,
                    cash_per_share=cash_per_share,
                    exchange_ratio=exchange_ratio,
                    synergy_run_rate=run_rate,
                    year_idx=year_idx,
                    deal_engine=deal_engine,
                    combine_engine=combine_engine,
                    target_book_equity=target_book_equity,
                    target_existing_goodwill=target_existing_goodwill,
                )
            )
        values.append(row)

    return SensitivityGrid(
        year_idx=year_idx,
        row_label="cash_fraction",
        col_label="synergies",
        row_values=list(cash_fractions),
        col_values=list(synergy_run_rates),
        values=values,
    )


def breakeven_synergies(
    terms: DealTerms,
    base_deal_assumptions: DealAssumptions,
    acquirer: StatementSet,
    target: StatementSet,
    *,
    year_idx: int = 0,
    deal_engine: DealEngineProto | None = None,
    combine_engine: CombinationEngineProto | None = None,
    target_book_equity: float = 0.0,
    target_existing_goodwill: float = 0.0,
    cap: float = _BREAKEVEN_CAP,
    tol: float = 1e-9,
) -> float | None:
    """Annual synergy run-rate (fully realized) that zeroes Year-``year_idx``
    A/D at the BASE consideration structure.

    A/D is linear in synergies, so a bisection between 0 and ``cap`` converges.
    Returns None if the root is not bracketed in ``[0, cap]`` (e.g. the deal is
    already accretive at zero synergies, or dilution exceeds what ``cap`` of
    synergies can offset)."""
    deal_engine = deal_engine or DealEngineImpl()
    combine_engine = combine_engine or CombinationEngine()

    cash_base = _require(terms.cash_per_share, "cash_per_share").value
    xratio_base = _require(terms.exchange_ratio, "exchange_ratio").value

    def f(run_rate: float) -> float:
        ad = _accretion_dilution(
            terms,
            base_deal_assumptions,
            acquirer,
            target,
            cash_per_share=cash_base,
            exchange_ratio=xratio_base,
            synergy_run_rate=run_rate,
            year_idx=year_idx,
            deal_engine=deal_engine,
            combine_engine=combine_engine,
            target_book_equity=target_book_equity,
            target_existing_goodwill=target_existing_goodwill,
        )
        if ad is None:
            raise ValueError("accretion/dilution is undefined (acquirer standalone EPS is zero)")
        return ad

    lo, hi = 0.0, cap
    f_lo, f_hi = f(lo), f(hi)
    if f_lo == 0.0:
        return 0.0
    if f_lo > 0.0 or f_hi < 0.0:
        return None  # root not bracketed in a sane range

    for _ in range(200):
        mid = 0.5 * (lo + hi)
        f_mid = f(mid)
        if abs(f_mid) <= tol or (hi - lo) <= tol:
            return mid
        if f_mid < 0.0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def build_sensitivities(bundle: MergerModelBundle, *, year_idx: int = 0) -> SensitivitySet:
    """Real-deal entry point: build both grids + breakeven from a
    :class:`~src.interfaces.MergerModelBundle`.

    Uses the SAME projected-column target book-equity / existing-goodwill figures
    the flagship deal engine consumes (first projected column), so the grids are
    consistent with the base model's PPA and pro forma balance sheet."""
    tgt = bundle.target_statements
    proj0 = tgt.n_hist  # first projected column, matching flagship
    target_book_equity = float(tgt.series(LineItem.TOTAL_EQUITY)[proj0] or 0.0)
    target_existing_goodwill = float(tgt.series(LineItem.GOODWILL)[proj0] or 0.0)

    terms = bundle.terms
    base_da = bundle.deal_assumptions
    acquirer = bundle.acquirer_statements
    target = bundle.target_statements
    deal_engine = DealEngineImpl()
    combine_engine = CombinationEngine()

    common = {
        "year_idx": year_idx,
        "deal_engine": deal_engine,
        "combine_engine": combine_engine,
        "target_book_equity": target_book_equity,
        "target_existing_goodwill": target_existing_goodwill,
    }

    premium_grid = premium_x_synergies_grid(terms, base_da, acquirer, target, **common)
    mix_grid = consideration_mix_grid(terms, base_da, acquirer, target, **common)
    breakeven = breakeven_synergies(terms, base_da, acquirer, target, **common)

    return SensitivitySet(
        premium_x_synergies=premium_grid,
        consideration_mix=mix_grid,
        breakeven_synergies=breakeven,
        breakeven_year_idx=year_idx,
    )
