"""The real Synopsys/ANSYS deal — bundle assembler (ORCH judgment core).

This is the single place the REAL-deal :class:`~src.interfaces.MergerModelBundle`
is assembled from cached SEC facts + the orchestrator's assumptions. Every
number it produces is engine-computed; every *assumption* it injects is argued in
``docs/ASSUMPTIONS.md`` §3 (2–4 line sourced rationale each). Disclosed deal
terms come from :func:`src.edgar.extract.extract_deal_terms` (provenance-stamped);
our modeling choices are the constants named ``*_OURS`` below.

Critical modeling decisions (see docs/ASSUMPTIONS.md):
* **Pre-close base year.** Standalone models are built from each company's last
  *pre-close* fiscal year — Synopsys FY2024 (2024-10-31) and ANSYS FY2024
  (2024-12-31). Synopsys FY2025 already consolidates ANSYS (goodwill $3.4B→$26.9B,
  LT debt →$13.46B), so using it would double-count the target; we slice it off.
* **Financing.** ~$14.3B new debt ($10.0B senior notes + $4.3B term loan,
  disclosed) + ~$3.05B cash on hand; blended new-debt rate 5.0% (ours).
* **PPA.** Write off ANSYS's existing goodwill, step up intangibles $8.0B (10-yr),
  DTL at 21% statutory; goodwill is the plug.
* **Target payout = 100%** post-close so its book equity stays flat and the pro
  forma balance sheet balances every period (a stated simplification).
* **Two synergy cases, both ours** (the proxy quantifies none): conservative
  $150M and base $300M annual run-rate.
"""

from __future__ import annotations

from src.combine import CombinationEngine
from src.deal import DealEngineImpl
from src.edgar import extract_deal_terms, extract_fairness_disclosures, load_normalized_facts
from src.interfaces import (
    DealAssumptions,
    MergerModelBundle,
    ProjectionAssumptions,
    StatementSet,
    SynergyCase,
    TerminalAssumptions,
    WACCInputs,
)
from src.precedents import load_precedents
from src.schema import CompanyMeta, DealTerms, LineItem
from src.standalone import ThreeStatementBuilder
from src.valuation import DCFValuationEngine

# As-of date stamped on the deliverables (deal announced 2024-01-16, closed
# 2025-07-17; this reconstruction is dated to the build).
AS_OF = "2026-08-08"

# --- Pre-close base-year cutoffs (see docstring / ASSUMPTIONS §3.0) ---------
_ACQUIRER_BASE_FY_END_YEAR = 2024  # Synopsys FY2024 ended 2024-10-31 (pre-close)
_TARGET_BASE_FY_END_YEAR = 2024  # ANSYS FY2024 ended 2024-12-31 (pre-close)

_N_PROJ_YEARS = 5

# --- Financing (structure disclosed; blended rate ours — ASSUMPTIONS §3.4) --
_NEW_DEBT_OURS = 14_300_000_000.0  # $10.0B notes + $4.3B term loan (disclosed)
_NEW_DEBT_RATE_OURS = 0.050  # blended IG-tech coupon (ours)
# Cash on hand funds the exact remainder of uses (equity purchase price + fees)
# after the disclosed $14.3B debt and the stock leg — so sources = uses with no
# residual plug and the pro forma balance sheet ties. ~$3.05B is well within
# Synopsys's ~$3.9B pre-close cash (ASSUMPTIONS §3.4).
_CASH_ON_HAND_USED_OURS = 3_048_096_257.0
_FOREGONE_CASH_YIELD_OURS = 0.040  # short-rate on deployed cash (ours)
_ADVISORY_FEES_OURS = 100_000_000.0  # ~0.3% of deal value (ours)
_FINANCING_FEES_OURS = 50_000_000.0  # (ours)

# --- Purchase price accounting (ours — ASSUMPTIONS §3.5) --------------------
_INTANGIBLE_STEP_UP_OURS = 8_000_000_000.0
_INTANGIBLE_LIFE_OURS = 10.0
_PPE_STEP_UP_OURS = 0.0
_PPE_LIFE_OURS = 0.0
_DEFERRED_TAX_RATE_OURS = 0.21  # US statutory on step-up basis difference

# --- Taxes (ours — ASSUMPTIONS §3.7) ----------------------------------------
_MARGINAL_TAX_OURS = 0.16

# --- Standalone ANSYS DCF inputs (ours — ASSUMPTIONS §3.9) -------------------
# CAPM: ~4.3% Rf + 1.05 beta × 5.0% ERP ≈ 9.55% (ANSYS ~net cash → WACC ≈ Ke).
_TGT_RISK_FREE_OURS = 0.043
_TGT_BETA_OURS = 1.05
_TGT_ERP_OURS = 0.050
_TGT_PRETAX_KD_OURS = 0.050
_TGT_TERMINAL_GROWTH_OURS = 0.030
_TGT_EXIT_EV_EBITDA_OURS = 22.0

# --- Synergy cases (both ours — ASSUMPTIONS §3.6) ---------------------------
_SYNERGY_CONSERVATIVE = SynergyCase(
    name="Conservative (ours)",
    run_rate_annual=150_000_000.0,
    phase_in=[0.33, 0.67, 1.0, 1.0, 1.0],
    is_disclosed=False,
)
_SYNERGY_BASE = SynergyCase(
    name="Base (ours)",
    run_rate_annual=300_000_000.0,
    phase_in=[0.50, 0.75, 1.0, 1.0, 1.0],
    is_disclosed=False,  # NOT management's figure — the proxy discloses none
)


def _acquirer_assumptions() -> ProjectionAssumptions:
    """Synopsys standalone drivers (ASSUMPTIONS §3.1)."""
    return ProjectionAssumptions(
        n_years=_N_PROJ_YEARS,
        revenue_growth=[0.11, 0.10, 0.10, 0.09, 0.09],
        gross_margin=[0.80, 0.80, 0.80, 0.80, 0.80],
        sga_pct_revenue=[0.13, 0.13, 0.13, 0.13, 0.13],
        rnd_pct_revenue=[0.34, 0.34, 0.34, 0.34, 0.34],
        dso=[70, 70, 70, 70, 70],
        dio=[10, 10, 10, 10, 10],
        dpo=[30, 30, 30, 30, 30],
        capex_pct_revenue=[0.025, 0.025, 0.025, 0.025, 0.025],
        da_pct_revenue=[0.04, 0.04, 0.04, 0.04, 0.04],
        tax_rate=[_MARGINAL_TAX_OURS] * _N_PROJ_YEARS,
        interest_rate_on_debt=0.045,
        interest_rate_on_cash=0.03,
        min_cash=500_000_000.0,
        dividend_payout=[0.0] * _N_PROJ_YEARS,  # Synopsys pays no dividend
    )


def _target_assumptions() -> ProjectionAssumptions:
    """ANSYS standalone drivers (ASSUMPTIONS §3.2). Payout=100% so book equity
    stays flat post-close and the pro forma BS balances every period (§3.2)."""
    return ProjectionAssumptions(
        n_years=_N_PROJ_YEARS,
        revenue_growth=[0.09, 0.08, 0.08, 0.07, 0.07],
        gross_margin=[0.89, 0.89, 0.89, 0.89, 0.89],
        sga_pct_revenue=[0.39, 0.39, 0.39, 0.39, 0.39],
        rnd_pct_revenue=[0.20, 0.20, 0.20, 0.20, 0.20],
        dso=[80, 80, 80, 80, 80],
        dio=[0, 0, 0, 0, 0],
        dpo=[30, 30, 30, 30, 30],
        capex_pct_revenue=[0.015, 0.015, 0.015, 0.015, 0.015],
        da_pct_revenue=[0.055, 0.055, 0.055, 0.055, 0.055],
        tax_rate=[_MARGINAL_TAX_OURS] * _N_PROJ_YEARS,
        interest_rate_on_debt=0.045,
        interest_rate_on_cash=0.03,
        min_cash=300_000_000.0,
        dividend_payout=[1.0] * _N_PROJ_YEARS,  # 100% payout → equity flat (§3.2)
    )


def _slice_to_base_year(hist: StatementSet, end_year: int) -> StatementSet:
    """Trim a historical StatementSet so its LAST column is the pre-close base
    fiscal year (dropping any later, post-close periods). Keeps all columns whose
    period end-year is <= ``end_year``."""
    keep = [i for i, p in enumerate(hist.periods) if p.end.year <= end_year]
    if not keep:
        raise ValueError(f"no historical period on/before FY{end_year}")
    last = keep[-1] + 1
    periods = hist.periods[:last]
    rows = {li: vals[:last] for li, vals in hist.rows.items()}
    return StatementSet(periods=periods, rows=rows, n_hist=len(periods))


def build_flagship_bundle(
    precedents_csv: str | None = None,
    *,
    with_sensitivities: bool = True,
    with_fairness: bool = True,
) -> MergerModelBundle:
    """Assemble the real Synopsys/ANSYS ``MergerModelBundle`` end-to-end.

    ``with_sensitivities`` / ``with_fairness`` attach the premium×synergies /
    consideration-mix grids + breakeven and the Qatalyst fairness differential;
    set them False for a faster base-only bundle (e.g. quick invariant checks).
    """
    builder = ThreeStatementBuilder()

    # --- Standalone models off the PRE-CLOSE base year ----------------------
    acq_facts = load_normalized_facts("SNPS")
    tgt_facts = load_normalized_facts("ANSS")
    acq_hist = _slice_to_base_year(builder.build_historical(acq_facts), _ACQUIRER_BASE_FY_END_YEAR)
    tgt_hist = _slice_to_base_year(builder.build_historical(tgt_facts), _TARGET_BASE_FY_END_YEAR)

    acq_assum = _acquirer_assumptions()
    tgt_assum = _target_assumptions()
    acq_stmts = builder.project(acq_hist, acq_assum)
    tgt_stmts = builder.project(tgt_hist, tgt_assum)

    # The standalone builder leaves projected diluted shares as an honest unknown;
    # the share plan sets them. Hold each company's base-year diluted count flat
    # across the projection (no standalone buyback/issuance modeled).
    for stmts in (acq_stmts, tgt_stmts):
        base_sh = stmts.series(LineItem.SHARES_DILUTED)[stmts.n_hist - 1]
        n_after = len(stmts.periods) - stmts.n_hist
        stmts.rows[LineItem.SHARES_DILUTED] = (
            stmts.rows[LineItem.SHARES_DILUTED][: stmts.n_hist] + [base_sh] * n_after
        )

    # --- Disclosed deal terms (provenance-stamped) --------------------------
    terms: DealTerms = extract_deal_terms()

    # --- Deal engine: consideration, S&U, PPA → goodwill --------------------
    # PPA must consume the SAME target equity the combination engine eliminates
    # from the pro forma balance sheet — namely the FIRST PROJECTED column, not
    # the reported base year. The standalone builder's seed-balancing step (it
    # absorbs the historical component gap into other-noncurrent-liabilities so
    # the projection starts square) makes projected equity differ from reported
    # equity by that plug; using the projected figure in both places keeps the
    # PPA goodwill and the pro forma BS elimination consistent, so the sheet
    # balances. Target book equity is flat across the projection (100% payout).
    tgt_proj0 = tgt_stmts.n_hist  # first projected column index
    tgt_book_equity = float(tgt_stmts.series(LineItem.TOTAL_EQUITY)[tgt_proj0] or 0.0)
    tgt_existing_gw = float(tgt_stmts.series(LineItem.GOODWILL)[tgt_proj0] or 0.0)
    # We do NOT model refinancing ANSYS's ~$0.75B legacy debt — it stays
    # outstanding on the pro forma balance sheet (Synopsys did not repay it as
    # part of the deal financing), so refinanced_target_debt = 0.
    tgt_lt_debt = 0.0

    # Target shares outstanding (disclosed) — used to gross up consideration and
    # for the standalone-DCF market cap below. The stock leg's new-share count is
    # computed inside the deal engine from exchange_ratio × target_shares.
    tgt_shares = terms.target_shares_outstanding.value if terms.target_shares_outstanding else 0.0

    deal_assum = DealAssumptions(
        new_debt=_NEW_DEBT_OURS,
        new_debt_rate=_NEW_DEBT_RATE_OURS,
        cash_on_hand_used=_CASH_ON_HAND_USED_OURS,
        foregone_cash_yield=_FOREGONE_CASH_YIELD_OURS,
        advisory_fees=_ADVISORY_FEES_OURS,
        financing_fees=_FINANCING_FEES_OURS,
        intangible_step_up=_INTANGIBLE_STEP_UP_OURS,
        intangible_useful_life_years=_INTANGIBLE_LIFE_OURS,
        ppe_step_up=_PPE_STEP_UP_OURS,
        ppe_useful_life_years=_PPE_LIFE_OURS,
        deferred_tax_rate=_DEFERRED_TAX_RATE_OURS,
        marginal_tax_rate=_MARGINAL_TAX_OURS,
    )
    deal = DealEngineImpl().build(
        terms,
        deal_assum,
        target_book_equity=tgt_book_equity,
        target_existing_goodwill=tgt_existing_gw,
        refinanced_target_debt=tgt_lt_debt,
    )

    # --- Combination: both synergy cases ------------------------------------
    engine = CombinationEngine()
    combinations = [
        engine.combine(acq_stmts, tgt_stmts, deal, deal_assum, _SYNERGY_BASE),
        engine.combine(acq_stmts, tgt_stmts, deal, deal_assum, _SYNERGY_CONSERVATIVE),
    ]

    # --- Precedents + fairness disclosures ----------------------------------
    precedents = load_precedents(precedents_csv) if precedents_csv else []
    fairness = extract_fairness_disclosures()

    bundle = MergerModelBundle(
        acquirer=CompanyMeta(cik=acq_facts.company.cik, ticker="SNPS", name=acq_facts.company.name),
        target=CompanyMeta(cik=tgt_facts.company.cik, ticker="ANSS", name=tgt_facts.company.name),
        terms=terms,
        acquirer_statements=acq_stmts,
        target_statements=tgt_stmts,
        acquirer_assumptions=acq_assum,
        target_assumptions=tgt_assum,
        deal_assumptions=deal_assum,
        deal=deal,
        combinations=combinations,
        precedents=precedents,
        fairness_disclosures=fairness,
    )

    # --- Standalone ANSYS DCF (our own target valuation — ASSUMPTIONS §3.9) ---
    # Market cap at the offered per-share value; ANSYS book debt is immaterial
    # (~net cash), so WACC ≈ cost of equity. Framed vs. the offer in the memo.
    tgt_base = tgt_stmts.n_hist - 1
    offered_px = terms.stated_price_per_share.value if terms.stated_price_per_share else 390.19
    tgt_market_cap = offered_px * tgt_shares
    tgt_total_debt = float(tgt_stmts.series(LineItem.LONG_TERM_DEBT)[tgt_base] or 0.0)
    bundle.target_dcf = DCFValuationEngine().dcf(
        tgt_stmts,
        WACCInputs(
            risk_free_rate=_TGT_RISK_FREE_OURS,
            beta=_TGT_BETA_OURS,
            equity_risk_premium=_TGT_ERP_OURS,
            pretax_cost_of_debt=_TGT_PRETAX_KD_OURS,
            tax_rate=_MARGINAL_TAX_OURS,
            market_cap=tgt_market_cap,
            total_debt=tgt_total_debt,
        ),
        TerminalAssumptions(
            method="both",
            terminal_growth=_TGT_TERMINAL_GROWTH_OURS,
            exit_ev_ebitda=_TGT_EXIT_EV_EBITDA_OURS,
            mid_year_convention=True,
        ),
    )

    # --- Sensitivities + fairness differential (computed off the base bundle) --
    # Imported lazily to avoid an import cycle (both packages import flagship's
    # sibling engines, not flagship itself; a top-level import here would be fine
    # but lazy keeps the fast path light for callers that skip them).
    if with_sensitivities:
        from src.scenarios import build_sensitivities

        bundle.sensitivities = build_sensitivities(bundle)
    if with_fairness:
        from src.fairness import run_fairness_differential
        from src.standalone import helpers

        net_debt = helpers.net_debt(tgt_stmts, tgt_stmts.n_hist - 1)
        shares = terms.target_shares_outstanding.value if terms.target_shares_outstanding else 0.0
        if shares:
            bundle.fairness_differential = run_fairness_differential(
                fairness[0], tgt_stmts, net_debt=net_debt, shares=shares
            )

    return bundle
