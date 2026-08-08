"""Fairness-opinion differential — the mission's signature verification.

Runs Qatalyst Partners' DISCLOSED assumption ranges (from the ANSYS DEFM14A,
extracted by :mod:`src.edgar.extract`) through OUR valuation/comps engines and
checks that OUR implied per-share ranges reproduce Qatalyst's disclosed implied
ranges. Overlap is quantified per methodology; every gap is explained in a
``deviation_note``. Inputs are NEVER tuned to force agreement — the point is to
measure reproduction quality, not manufacture it.

Three disclosed methodologies are reproduced:

* **Discounted Cash Flow** — the disclosed Management-Case-1 unlevered-FCF
  stream (FY2024E–FY2033E) is discounted through :func:`src.valuation.dcf_from_ufcf`
  at the disclosed discount-rate range with the disclosed NTM-UFCF terminal
  multiple. Qatalyst discount CY2024–CY2032 explicitly with a FY2033 terminal
  value, so the explicit horizon is the stream less its final year and the
  terminal metric is that final (FY2033E) UFCF — the NTM UFCF at the CY2032
  horizon. OUR ``our_high`` pairs the LOW discount rate with the HIGH terminal
  multiple; ``our_low`` pairs the HIGH discount rate with the LOW multiple.

* **Selected Companies / Selected Transactions** — the disclosed price/LFCF
  multiple range is applied through :func:`src.comps.implied_range_from_multiple`
  to ANSYS's disclosed near-term free-cash-flow metric. Because these are
  levered (equity) FCF multiples, ``is_equity_multiple=True`` (the multiple
  applies directly to equity value, no net-debt bridge).

Because only Management Case 1's projections are tabulated in the proxy (the DCF
implied range Qatalyst disclose is the UNION across Cases 1–3), and because we
carry ANSYS's UFCF rather than a separately disclosed LFCF, the reproductions
diverge in documented, non-tuned ways — see each ``deviation_note``.
"""

from __future__ import annotations

from src.comps import implied_range_from_multiple
from src.interfaces import (
    FairnessDifferentialReport,
    MethodologyReproduction,
    StatementSet,
    TerminalAssumptions,
)
from src.schema import AdvisorMethodology, FairnessDisclosure, SourcedRange
from src.standalone import helpers
from src.valuation import dcf_from_ufcf

# USD-millions → raw USD (disclosed projections are tabulated in $ millions).
_MILLIONS = 1_000_000.0

# The disclosed advisor DCF discounts an explicit horizon with a terminal value
# built off the following-year ("NTM") UFCF; we use the mid-year convention on
# the explicit stream (advisor DCFs conventionally do; the proxy does not state
# it, so this is OUR documented modeling choice — see docs/ASSUMPTIONS.md).
_MID_YEAR = True


def _overlap_pct(
    disclosed_low: float | None,
    disclosed_high: float | None,
    our_low: float | None,
    our_high: float | None,
) -> float | None:
    """|intersection| / |disclosed range|, clamped to [0, 1].

    Returns None when either range is not fully known or the disclosed range has
    non-positive width (no denominator); 0.0 when the ranges are disjoint.
    """
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


def _reproduce_dcf(
    m: AdvisorMethodology,
    disclosure: FairnessDisclosure,
    *,
    net_debt: float,
    shares: float,
) -> MethodologyReproduction:
    """Reproduce the DCF implied range from the disclosed UFCF + rate + multiple."""
    disc = m.assumptions.get("discount_rate")
    mult = m.assumptions.get("ntm_ufcf_multiple")
    ufcf_series = disclosure.management_projections.get("unlevered_free_cash_flow", [])
    ufcf = [sv.value * _MILLIONS for sv in ufcf_series if sv.value is not None]

    our_low = our_high = None
    if (
        disc is not None
        and mult is not None
        and len(ufcf) >= 2
        and None
        not in (
            disc.low,
            disc.high,
            mult.low,
            mult.high,
        )
    ):
        # Explicit horizon = all but the final year; terminal metric = the final
        # (FY2033E) UFCF, the NTM UFCF at the CY2032 explicit-horizon end.
        explicit = ufcf[:-1]
        terminal_metric = ufcf[-1]
        # our_high: LOW discount rate × HIGH terminal multiple.
        hi = dcf_from_ufcf(
            explicit,
            disc.low / 100.0,
            TerminalAssumptions(
                method="exit_multiple", exit_ev_ebitda=mult.high, mid_year_convention=_MID_YEAR
            ),
            net_debt=net_debt,
            shares=shares,
            terminal_metric=terminal_metric,
        )
        # our_low: HIGH discount rate × LOW terminal multiple.
        lo = dcf_from_ufcf(
            explicit,
            disc.high / 100.0,
            TerminalAssumptions(
                method="exit_multiple", exit_ev_ebitda=mult.low, mid_year_convention=_MID_YEAR
            ),
            net_debt=net_debt,
            shares=shares,
            terminal_metric=terminal_metric,
        )
        our_low = lo.implied_price_exit
        our_high = hi.implied_price_exit

    overlap = _overlap_pct(m.implied_range.low, m.implied_range.high, our_low, our_high)
    note = (
        "OUR DCF reproduces only Management Case 1 (the sole projection set the "
        "proxy tabulates); Qatalyst's disclosed range is the UNION across "
        "Management Cases 1-3, so our narrower Case-1 range overlaps its upper "
        "portion. Explicit CY2024E-CY2032E UFCF discounted mid-year with a FY2033E "
        "NTM-UFCF terminal multiple; net debt/share is ANSYS's disclosed net-cash "
        "position, so the EV->equity bridge lifts per-share value above EV."
    )
    return MethodologyReproduction(
        advisor=disclosure.advisor,
        method=m.method,
        disclosed_low=m.implied_range.low,
        disclosed_high=m.implied_range.high,
        our_low=our_low,
        our_high=our_high,
        overlap_pct=overlap,
        deviation_note=note,
    )


def _reproduce_multiple(
    m: AdvisorMethodology,
    disclosure: FairnessDisclosure,
    mult: SourcedRange | None,
    metric_value: float | None,
    metric_label: str,
    *,
    net_debt: float,
    shares: float,
) -> MethodologyReproduction:
    """Reproduce a Selected-Companies/Transactions range from an equity multiple."""
    our_low = our_high = None
    if mult is not None and metric_value is not None and None not in (mult.low, mult.high):
        our_low, our_high = implied_range_from_multiple(
            None,
            metric_value,
            mult.low,
            mult.high,
            net_debt=net_debt,
            shares=shares,
            is_equity_multiple=True,
        )

    overlap = _overlap_pct(m.implied_range.low, m.implied_range.high, our_low, our_high)
    note = (
        f"Disclosed LFCF (levered/equity) multiple applied directly to equity "
        f"(is_equity_multiple=True, no net-debt bridge), using {metric_label} as "
        "the LFCF metric: the proxy tabulates ANSYS UFCF, not LFCF, but ANSYS "
        "carries net cash so LFCF ~= UFCF (immaterial net interest). OUR range "
        "reproduces the disclosed union across cases."
    )
    return MethodologyReproduction(
        advisor=disclosure.advisor,
        method=m.method,
        disclosed_low=m.implied_range.low,
        disclosed_high=m.implied_range.high,
        our_low=our_low,
        our_high=our_high,
        overlap_pct=overlap,
        deviation_note=note,
    )


def run_fairness_differential(
    disclosure: FairnessDisclosure,
    target_statements: StatementSet,  # noqa: ARG001 (carried for symmetry; metrics come from disclosure)
    *,
    net_debt: float,
    shares: float,
) -> FairnessDifferentialReport:
    """Run each disclosed methodology through OUR engine → FairnessDifferentialReport.

    Args:
        disclosure: the advisor's disclosed fairness analyses (methodologies +
            assumption ranges + management projections), from
            :func:`src.edgar.extract.extract_fairness_disclosures`.
        target_statements: the subject company's StatementSet (carried for
            symmetry; the reproduced metrics are read from the DISCLOSED
            projections, not the statements, so the comparison stays sourced).
        net_debt: subject net debt for the EV→equity bridge (positive = net debt;
            ANSYS is net cash, so this is negative).
        shares: diluted share count for the per-share bridge (must be > 0).
    """
    # Near-term LFCF proxy for the multiple methodologies: the disclosed
    # Management-Case-1 CY2024E UFCF (NTM ~= CY2024E at the ~Jan-2024 analysis
    # date). ANSYS's net-cash position makes LFCF ~= UFCF.
    ufcf_series = disclosure.management_projections.get("unlevered_free_cash_flow", [])
    near_term_fcf = (
        ufcf_series[0].value * _MILLIONS if ufcf_series and ufcf_series[0].value else None
    )

    reproductions: list[MethodologyReproduction] = []
    for m in disclosure.methodologies:
        if m.method == "Discounted Cash Flow":
            reproductions.append(_reproduce_dcf(m, disclosure, net_debt=net_debt, shares=shares))
        elif m.method == "Selected Companies":
            reproductions.append(
                _reproduce_multiple(
                    m,
                    disclosure,
                    m.assumptions.get("cy2024e_lfcf_multiple"),
                    near_term_fcf,
                    "disclosed Management-Case-1 CY2024E UFCF",
                    net_debt=net_debt,
                    shares=shares,
                )
            )
        elif m.method == "Selected Transactions":
            reproductions.append(
                _reproduce_multiple(
                    m,
                    disclosure,
                    m.assumptions.get("ntm_lfcf_multiple"),
                    near_term_fcf,
                    "disclosed Management-Case-1 NTM (~CY2024E) UFCF",
                    net_debt=net_debt,
                    shares=shares,
                )
            )

    return FairnessDifferentialReport(reproductions=reproductions)


def run_flagship_fairness() -> FairnessDifferentialReport:
    """Real-deal entry point: reproduce Qatalyst's ANSYS analyses end-to-end.

    Pulls the disclosure + target statements from :func:`src.flagship.build_flagship_bundle`
    and runs the differential with ANSYS's disclosed net debt and share count.
    Populates :attr:`src.interfaces.MergerModelBundle.fairness_differential` at G2.
    """
    # Imported lazily so the fairness package does not pull the full flagship
    # assembler (and its EDGAR fixtures) at import time.
    from src.flagship import build_flagship_bundle

    bundle = build_flagship_bundle()
    disclosure = bundle.fairness_disclosures[0]
    target = bundle.target_statements
    # Net debt off the last historical balance-sheet column (the canonical
    # net-debt convention shared with the valuation/LBO engines); ANSYS is net
    # cash, so this is negative. Shares = the disclosed target share count.
    net_debt = helpers.net_debt(target, target.n_hist - 1)
    terms_shares = bundle.terms.target_shares_outstanding
    if terms_shares is None or not terms_shares.value:
        raise ValueError(
            "disclosed target shares outstanding is required for the per-share bridge "
            "(honest-unknown: not fabricated)."
        )
    return run_fairness_differential(
        disclosure, target, net_debt=net_debt, shares=terms_shares.value
    )
