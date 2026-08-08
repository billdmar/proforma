"""Deal #2 — the real Cisco/Splunk deal — bundle assembler (P6 generality proof).

Parallel to :mod:`src.flagship` (Synopsys/ANSYS). It reuses EVERY engine
unchanged — :class:`~src.standalone.ThreeStatementBuilder`,
:class:`~src.deal.DealEngineImpl`, :class:`~src.combine.CombinationEngine`,
:class:`~src.valuation.DCFValuationEngine`, :func:`~src.edgar.load_normalized_facts`,
:func:`~src.scenarios.build_sensitivities`, and the valuation/comps primitives
underlying the fairness differential — and changes ONLY the deal-specific wiring
(inputs, extraction entry points, and the advisor-taxonomy dispatch). Every
number it produces is engine-computed; every *assumption* it injects is argued in
``docs/ASSUMPTIONS_CSCO_SPLK.md`` §3. Disclosed deal terms come from
:func:`src.edgar.extract_deal_terms_csco_splk` (provenance-stamped); our modeling
choices are the constants named ``*_OURS`` below.

Why this deal is a different shape (ASSUMPTIONS_CSCO_SPLK §Why):
* **All cash.** $157.00/share, no stock leg — ``exchange_ratio`` and
  ``reference_acquirer_price`` are honest ``None`` in the disclosed terms, so the
  deal engine's stock leg is zero and no new acquirer shares are issued.
* **Loss-making, negative-book-equity target.** Splunk's FY2023 book equity is
  −$110.5M and it was operating at a ~−6.4% margin at base. Carried as-is into
  the PPA: almost the entire purchase price becomes intangibles + goodwill, and
  the combination is heavily dilutive early (the honest, correct result — a
  strategic/growth bet, not an EPS deal). Nothing is tuned to look better.
* **Two advisors** (Qatalyst Partners AND Morgan Stanley), both reproduced.

Critical modeling decisions (see docs/ASSUMPTIONS_CSCO_SPLK.md):
* **Pre-close base year.** Standalone models are built from each company's last
  *pre-close* fiscal year — Cisco FY2023 (2023-07-29) and Splunk FY2023
  (2023-01-31). Cisco FY2024/FY2025 already consolidate Splunk (goodwill jumps
  to ~$58.7B), so using them would double-count the target; we slice them off.
* **Financing.** $22.0B new senior notes (disclosed) at a blended 5.0% (ours) +
  cash on hand funding the exact remainder so sources = uses with no plug.
* **PPA.** Write off Splunk's existing $1.42B goodwill, step up intangibles
  $9.0B (10-yr), DTL at 21% statutory; goodwill is the plug.
* **Target payout = 100%** post-close so its book equity stays flat and the pro
  forma balance sheet balances every period (a stated simplification).
* **Two synergy cases, both ours** (the proxy quantifies none): conservative
  $200M and base $400M annual run-rate.
"""

from __future__ import annotations

from src.combine import CombinationEngine
from src.comps import implied_range_from_multiple
from src.deal import DealEngineImpl
from src.edgar import (
    extract_deal_terms_csco_splk,
    extract_fairness_disclosures_csco_splk,
    load_normalized_facts,
)
from src.interfaces import (
    DealAssumptions,
    FairnessDifferentialReport,
    MergerModelBundle,
    MethodologyReproduction,
    ProjectionAssumptions,
    StatementSet,
    SynergyCase,
    TerminalAssumptions,
    WACCInputs,
)
from src.precedents import load_precedents
from src.schema import AdvisorMethodology, CompanyMeta, DealTerms, FairnessDisclosure, LineItem
from src.standalone import ThreeStatementBuilder
from src.valuation import DCFValuationEngine, dcf_from_ufcf

# As-of date stamped on the deliverables (deal announced 2023-09-21, closed
# 2024-03-18; this reconstruction is dated to the build).
AS_OF = "2026-08-08"

# --- Pre-close base-year cutoffs (see docstring / ASSUMPTIONS §2) -----------
_ACQUIRER_BASE_FY_END_YEAR = 2023  # Cisco FY2023 ended 2023-07-29 (pre-close)
_TARGET_BASE_FY_END_YEAR = 2023  # Splunk FY2023 ended 2023-01-31 (pre-close)

_N_PROJ_YEARS = 5

# --- Financing (structure disclosed; blended rate ours — ASSUMPTIONS §3.3) --
_NEW_DEBT_OURS = 22_000_000_000.0  # $22.0B senior notes issued Feb 2024 (disclosed)
_NEW_DEBT_RATE_OURS = 0.050  # blended 2024 IG-tech coupon across tranches (ours)
_FOREGONE_CASH_YIELD_OURS = 0.040  # short-rate on deployed cash (ours)
_ADVISORY_FEES_OURS = 100_000_000.0  # (ours)
_FINANCING_FEES_OURS = 50_000_000.0  # (ours)
# Cash on hand funds the exact remainder of uses (equity purchase price + fees)
# after the disclosed $22.0B debt and the stock leg (zero here — all cash), so
# sources = uses with no residual plug and the pro forma balance sheet ties.
# Computed below from the disclosed consideration rather than hard-coded.

# --- Purchase price accounting (ours — ASSUMPTIONS §3.4) --------------------
_INTANGIBLE_STEP_UP_OURS = 9_000_000_000.0
_INTANGIBLE_LIFE_OURS = 10.0
_PPE_STEP_UP_OURS = 0.0
_PPE_LIFE_OURS = 0.0
_DEFERRED_TAX_RATE_OURS = 0.21  # US statutory on step-up basis difference

# --- Taxes (ours — ASSUMPTIONS §3.6) ----------------------------------------
_MARGINAL_TAX_OURS = 0.16

# --- Standalone Splunk DCF inputs (ours — ASSUMPTIONS §3, target-valuation) --
# CAPM: ~4.3% Rf + 1.20 beta × 5.0% ERP. Splunk is a higher-beta growth-software
# name than ANSYS; Splunk carries ~no LT debt so WACC ≈ cost of equity. Splunk is
# barely profitable at base, so this DCF is a growth-DCF STRESS case — reported
# honestly, not tuned.
_TGT_RISK_FREE_OURS = 0.043
_TGT_BETA_OURS = 1.20
_TGT_ERP_OURS = 0.050
_TGT_PRETAX_KD_OURS = 0.050
_TGT_TERMINAL_GROWTH_OURS = 0.030
_TGT_EXIT_EV_EBITDA_OURS = 22.0

# --- Synergy cases (both ours — ASSUMPTIONS §3.5) ---------------------------
_SYNERGY_CONSERVATIVE = SynergyCase(
    name="Conservative (ours)",
    run_rate_annual=200_000_000.0,
    phase_in=[0.33, 0.67, 1.0, 1.0, 1.0],
    is_disclosed=False,
)
_SYNERGY_BASE = SynergyCase(
    name="Base (ours)",
    run_rate_annual=400_000_000.0,
    phase_in=[0.50, 0.75, 1.0, 1.0, 1.0],
    is_disclosed=False,  # NOT management's figure — the proxy discloses none
)

# USD-millions → raw USD (disclosed advisor projections are tabulated in $mm).
_MILLIONS = 1_000_000.0
# Advisor DCFs conventionally discount the explicit stream mid-year; the proxy
# does not state it, so this is OUR documented modeling choice (mirrors the
# deal-#1 fairness module).
_FAIRNESS_MID_YEAR = True


def _acquirer_assumptions() -> ProjectionAssumptions:
    """Cisco standalone drivers (ASSUMPTIONS §3.1).

    Mature networking/software leader: low-single-digit revenue growth and a
    flat ~26% operating margin (FY23 level). Margin = gross_margin − sga% − rnd%
    = 0.62 − 0.23 − 0.13 = 0.26 (Cisco FY23 gross margin ≈ 62%). Payout ~50%.
    ~4.07B diluted shares held flat (no standalone buyback modeled)."""
    return ProjectionAssumptions(
        n_years=_N_PROJ_YEARS,
        revenue_growth=[0.04, 0.04, 0.035, 0.03, 0.03],
        gross_margin=[0.62, 0.62, 0.62, 0.62, 0.62],
        sga_pct_revenue=[0.23, 0.23, 0.23, 0.23, 0.23],
        rnd_pct_revenue=[0.13, 0.13, 0.13, 0.13, 0.13],
        dso=[60, 60, 60, 60, 60],
        dio=[30, 30, 30, 30, 30],
        dpo=[30, 30, 30, 30, 30],
        capex_pct_revenue=[0.015, 0.015, 0.015, 0.015, 0.015],
        da_pct_revenue=[0.03, 0.03, 0.03, 0.03, 0.03],
        tax_rate=[_MARGINAL_TAX_OURS] * _N_PROJ_YEARS,
        interest_rate_on_debt=0.045,
        interest_rate_on_cash=0.03,
        min_cash=5_000_000_000.0,
        dividend_payout=[0.5] * _N_PROJ_YEARS,  # Cisco pays a large dividend
    )


def _target_assumptions() -> ProjectionAssumptions:
    """Splunk standalone drivers (ASSUMPTIONS §3.2) — the judgment call.

    Splunk was unprofitable at base but rapidly approaching breakeven. We model a
    credible margin ramp to profitability by holding gross margin flat at ~80%
    and DECLINING opex (SG&A + R&D) as a % of revenue year by year, so the EBIT
    margin (gross_margin − sga% − rnd%) ramps 2%→18% over five years:
      Y1: 0.80 − 0.50 − 0.28 = 0.02   Y2: 0.80 − 0.46 − 0.28 = 0.06
      Y3: 0.80 − 0.44 − 0.26 = 0.10   Y4: 0.80 − 0.42 − 0.24 = 0.14
      Y5: 0.80 − 0.40 − 0.22 = 0.18
    Payout=100% so book equity stays flat post-close and the pro forma BS
    balances every period (§3.2). ~162.4M diluted shares held flat."""
    return ProjectionAssumptions(
        n_years=_N_PROJ_YEARS,
        revenue_growth=[0.15, 0.13, 0.12, 0.10, 0.10],
        gross_margin=[0.80, 0.80, 0.80, 0.80, 0.80],
        sga_pct_revenue=[0.50, 0.46, 0.44, 0.42, 0.40],  # declining → margin ramp
        rnd_pct_revenue=[0.28, 0.28, 0.26, 0.24, 0.22],  # declining → margin ramp
        dso=[80, 80, 80, 80, 80],
        dio=[0, 0, 0, 0, 0],
        dpo=[30, 30, 30, 30, 30],
        capex_pct_revenue=[0.02, 0.02, 0.02, 0.02, 0.02],
        da_pct_revenue=[0.06, 0.06, 0.06, 0.06, 0.06],
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


# --- Fairness differential (deal-specific wiring; reuses unchanged engines) ---
# The deal-#1 orchestrator ``src.fairness.run_fairness_differential`` dispatches
# on ANSYS's disclosed method taxonomy (method names "Selected Companies" /
# "Selected Transactions" and exit-multiple assumption keys like
# "ntm_ufcf_multiple"). Splunk's two advisors disclose a DIFFERENT taxonomy —
# perpetuity-growth DCFs, a CY2024E revenue multiple, and method names "Public
# Trading Comparables" / "Precedent Transactions" — so that orchestrator returns
# all-``None`` here. Per the P6 contract ("reuse EVERY engine unchanged; only
# deal-specific wiring is new"), we keep src.fairness untouched and reproduce the
# Splunk advisors through the SAME underlying primitives the orchestrator itself
# calls — :func:`src.valuation.dcf_from_ufcf` and
# :func:`src.comps.implied_range_from_multiple` — with the Splunk-specific
# dispatch below. Overlap is quantified per methodology; where the proxy
# discloses an implied range but no reproducible assumption set for a sub-analysis
# (Selected/Precedent Transactions, Public Trading Comparables), our range is an
# honest ``None`` with a deviation note. Nothing is tuned to force agreement.


def _overlap_pct(
    disclosed_low: float | None,
    disclosed_high: float | None,
    our_low: float | None,
    our_high: float | None,
) -> float | None:
    """|intersection| / |disclosed range|, clamped to [0, 1]. None if any bound is
    unknown or the disclosed range has non-positive width; 0.0 if disjoint."""
    if None in (disclosed_low, disclosed_high, our_low, our_high):
        return None
    assert disclosed_low is not None and disclosed_high is not None
    assert our_low is not None and our_high is not None
    width = disclosed_high - disclosed_low
    if width <= 0:
        return None
    intersection = min(disclosed_high, our_high) - max(disclosed_low, our_low)
    if intersection <= 0:
        return 0.0
    return max(0.0, min(1.0, intersection / width))


def _reproduce_methodology(
    m: AdvisorMethodology,
    disclosure: FairnessDisclosure,
    *,
    ufcf: list[float],
    revenue_ntm: float | None,
    net_debt: float,
    shares: float,
) -> MethodologyReproduction:
    """Reproduce one Splunk advisor methodology through the unchanged primitives."""
    our_low = our_high = None
    note = ""

    disc = m.assumptions.get("discount_rate")
    perp = m.assumptions.get("perpetuity_growth")
    rev_mult = m.assumptions.get("cy2024e_revenue_multiple")

    if m.method == "Discounted Cash Flow" and disc and perp and len(ufcf) >= 2:
        if None not in (disc.low, disc.high, perp.low, perp.high):
            # Full disclosed UFCF stream discounted explicitly + a Gordon
            # perpetuity on the terminal-year UFCF (the advisors use a perpetuity
            # growth rate, not an exit multiple). our_high pairs the LOW discount
            # rate with the HIGH perpetuity growth; our_low the HIGH rate/LOW growth.
            hi = dcf_from_ufcf(
                ufcf,
                disc.low / 100.0,
                TerminalAssumptions(
                    method="gordon",
                    terminal_growth=perp.high / 100.0,
                    mid_year_convention=_FAIRNESS_MID_YEAR,
                ),
                net_debt=net_debt,
                shares=shares,
            )
            lo = dcf_from_ufcf(
                ufcf,
                disc.high / 100.0,
                TerminalAssumptions(
                    method="gordon",
                    terminal_growth=perp.low / 100.0,
                    mid_year_convention=_FAIRNESS_MID_YEAR,
                ),
                net_debt=net_debt,
                shares=shares,
            )
            our_low, our_high = lo.implied_price_gordon, hi.implied_price_gordon
            note = (
                "Disclosed management-case UFCF (FY2024E–FY2034E) discounted "
                "mid-year at the disclosed discount-rate band with a Gordon "
                "perpetuity at the disclosed growth band; Splunk's net-cash "
                "position lifts per-share value above EV. Our range reproduces "
                "the disclosed union across the advisor's projection scenarios."
            )
    elif (
        rev_mult is not None
        and revenue_ntm is not None
        and None
        not in (
            rev_mult.low,
            rev_mult.high,
        )
    ):
        # Selected-companies revenue multiple applied to disclosed FY2024E
        # revenue as an EV multiple (net-debt bridge to equity).
        our_low, our_high = implied_range_from_multiple(
            None,
            revenue_ntm,
            rev_mult.low,
            rev_mult.high,
            net_debt=net_debt,
            shares=shares,
            is_equity_multiple=False,
        )
        note = (
            "Disclosed CY2024E EV/revenue multiple range applied to the disclosed "
            "FY2024E revenue, bridged EV→equity at Splunk's net cash. The proxy's "
            "disclosed implied range is the union across its revenue AND LFCF "
            "multiple tables, so our revenue-only range sits inside the wider band."
        )
    else:
        note = (
            "The proxy discloses an implied per-share range for this sub-analysis "
            "but not a single reproducible assumption set (e.g. the union across "
            "several NTM revenue/EBITDA/LFCF tables), so our range is an honest "
            "None rather than a tuned fit; the disclosed range is retained for "
            "reference."
        )

    return MethodologyReproduction(
        advisor=disclosure.advisor,
        method=m.method,
        disclosed_low=m.implied_range.low,
        disclosed_high=m.implied_range.high,
        our_low=our_low,
        our_high=our_high,
        overlap_pct=_overlap_pct(m.implied_range.low, m.implied_range.high, our_low, our_high),
        deviation_note=note,
    )


def _reproduce_fairness(
    disclosures: list[FairnessDisclosure],
    *,
    net_debt: float,
    shares: float,
) -> FairnessDifferentialReport:
    """Reproduce BOTH Splunk advisors' disclosed analyses into one report.

    The reproductions list carries every methodology from both advisors (each
    ``MethodologyReproduction`` is stamped with its ``advisor``), so a per-advisor
    overlap is a simple filter and ``mean_overlap`` spans the reproducible set."""
    reproductions: list[MethodologyReproduction] = []
    for disclosure in disclosures:
        ufcf_series = disclosure.management_projections.get("unlevered_free_cash_flow", [])
        ufcf = [sv.value * _MILLIONS for sv in ufcf_series if sv.value is not None]
        rev_series = disclosure.management_projections.get("revenue", [])
        revenue_ntm = (
            rev_series[0].value * _MILLIONS if rev_series and rev_series[0].value else None
        )
        for m in disclosure.methodologies:
            reproductions.append(
                _reproduce_methodology(
                    m,
                    disclosure,
                    ufcf=ufcf,
                    revenue_ntm=revenue_ntm,
                    net_debt=net_debt,
                    shares=shares,
                )
            )
    return FairnessDifferentialReport(reproductions=reproductions)


def build_flagship_bundle(
    precedents_csv: str | None = None,
    *,
    with_sensitivities: bool = True,
    with_fairness: bool = True,
) -> MergerModelBundle:
    """Assemble the real Cisco/Splunk ``MergerModelBundle`` end-to-end.

    ``with_sensitivities`` / ``with_fairness`` attach the premium×synergies /
    consideration-mix grids + breakeven and the two-advisor fairness differential;
    set them False for a faster base-only bundle (e.g. quick invariant checks)."""
    builder = ThreeStatementBuilder()

    # --- Standalone models off the PRE-CLOSE base year ----------------------
    acq_facts = load_normalized_facts("CSCO")
    tgt_facts = load_normalized_facts("SPLK")
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
    terms: DealTerms = extract_deal_terms_csco_splk()

    # --- Deal engine: consideration, S&U, PPA → goodwill --------------------
    # PPA must consume the SAME target equity the combination engine eliminates
    # from the pro forma balance sheet — the FIRST PROJECTED column, not the
    # reported base year (see src.flagship for the seed-balancing rationale). For
    # Splunk that projected equity is NEGATIVE (−$110.5M reported, carried as-is),
    # which — with the $1.42B existing goodwill written off — makes goodwill large
    # and correct: almost the entire price is intangibles + goodwill. Target book
    # equity is flat across the projection (100% payout).
    tgt_proj0 = tgt_stmts.n_hist  # first projected column index
    tgt_book_equity = float(tgt_stmts.series(LineItem.TOTAL_EQUITY)[tgt_proj0] or 0.0)
    tgt_existing_gw = float(tgt_stmts.series(LineItem.GOODWILL)[tgt_proj0] or 0.0)
    # We do NOT model refinancing Splunk's legacy convertible debt as part of the
    # deal financing — it stays outstanding on the pro forma balance sheet.
    tgt_lt_debt = 0.0

    # All-cash: aggregate cash consideration + fees, funded by disclosed new debt
    # and cash on hand. cash_on_hand fills the exact remainder so sources = uses
    # with no plug and the pro forma BS ties (mirrors deal #1's exact-funding).
    cash_per_share = terms.cash_per_share.value if terms.cash_per_share else 0.0
    tgt_shares = terms.target_shares_outstanding.value if terms.target_shares_outstanding else 0.0
    equity_purchase_price = cash_per_share * tgt_shares
    fees = _ADVISORY_FEES_OURS + _FINANCING_FEES_OURS
    # No stock leg (all cash), so cash_on_hand = uses − new_debt − stock(0).
    cash_on_hand_used = equity_purchase_price + fees - _NEW_DEBT_OURS

    deal_assum = DealAssumptions(
        new_debt=_NEW_DEBT_OURS,
        new_debt_rate=_NEW_DEBT_RATE_OURS,
        cash_on_hand_used=cash_on_hand_used,
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
    fairness = extract_fairness_disclosures_csco_splk()

    bundle = MergerModelBundle(
        acquirer=CompanyMeta(cik=acq_facts.company.cik, ticker="CSCO", name=acq_facts.company.name),
        target=CompanyMeta(cik=tgt_facts.company.cik, ticker="SPLK", name=tgt_facts.company.name),
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

    # --- Standalone Splunk DCF (our own target valuation) -------------------
    # Market cap at the offered per-share value; Splunk carries ~no LT debt, so
    # WACC ≈ cost of equity. Splunk is barely profitable at base, so this is a
    # growth-DCF stress case — framed vs. the offer in the memo, reported honestly.
    offered_px = terms.stated_price_per_share.value if terms.stated_price_per_share else 157.00
    tgt_market_cap = offered_px * tgt_shares
    tgt_total_debt = float(tgt_stmts.series(LineItem.LONG_TERM_DEBT)[tgt_stmts.n_hist - 1] or 0.0)
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
    if with_sensitivities:
        bundle.sensitivities = _build_sensitivities_all_cash(bundle)
    if with_fairness:
        from src.standalone import helpers

        net_debt = helpers.net_debt(tgt_stmts, tgt_stmts.n_hist - 1)
        if tgt_shares:
            bundle.fairness_differential = _reproduce_fairness(
                fairness, net_debt=net_debt, shares=tgt_shares
            )

    return bundle


def _build_sensitivities_all_cash(bundle: MergerModelBundle):
    """Build the sensitivity set for the all-cash deal.

    :func:`src.scenarios.build_sensitivities` (unchanged) requires the stock-leg
    terms ``exchange_ratio`` and ``reference_acquirer_price`` to sweep premium and
    consideration-mix. Those are honest ``None`` for an all-cash deal, so we pass
    a copy of the disclosed terms augmented with a zero exchange ratio and a
    hypothetical acquirer reference price used ONLY to parameterize the
    consideration-mix axis (labeled ours). The base column (100% cash / disclosed
    premium) reproduces the real deal; the part-stock columns are a "what-if" the
    memo frames explicitly. No engine code changes."""
    from dataclasses import replace
    from datetime import date

    from src.scenarios import build_sensitivities
    from src.schema import DocProvenance, SourcedValue

    prov = DocProvenance(
        accession="OURS",
        form="N/A",
        filed=date.fromisoformat(AS_OF),
        section="ASSUMPTIONS_CSCO_SPLK §3 (ours)",
        quote=(
            "All-cash deal has no disclosed stock leg; a zero exchange ratio and a "
            "hypothetical acquirer reference price parameterize the "
            "consideration-mix sensitivity only (labeled ours)."
        ),
    )
    zero_xratio = SourcedValue(
        value=0.0, provenance=prov, unit="ratio", label="all-cash: no stock leg (ours)"
    )
    ref_price = SourcedValue(
        value=50.0,
        provenance=prov,
        unit="USD/share",
        label="hypothetical Cisco reference price for the part-stock mix what-if (ours)",
    )
    augmented = replace(
        bundle.terms, exchange_ratio=zero_xratio, reference_acquirer_price=ref_price
    )
    aug_bundle = replace(bundle, terms=augmented)
    return build_sensitivities(aug_bundle)
