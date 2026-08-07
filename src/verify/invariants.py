"""Deal-invariant runner (G1 onward).

Checks the structural identities that must hold in any correct merger model,
computed independently of the engines that produced them so the gate is a
genuine second opinion (mirrors the thesis project's accounting-invariant
runner in ``src/verify/invariants.py``, retargeted to the deal/combination
engines' outputs):

* **sources = uses** — the financing raised funds the purchase price + fees.
* **goodwill ties** — goodwill is the plug: equity purchase price − net
  identifiable assets.
* **pro forma balance sheet balances** — Assets = Liabilities + Equity, every
  projected period.
* **EPS bridge recomputes** — pro forma net income independently reassembled
  from the bridge's own components reproduces each year's pro forma EPS.
* **contribution ties** — pro forma ownership percentages sum to 1.0.
* **synergy phase-in** — the realized synergy in each bridge year equals the
  synergy case's phased-in run-rate, and the ramp reaches the run-rate at
  steady state.

Each check returns per-unit residuals; the runner asserts every residual is
within its tolerance ($1 for balance-sheet dollars, $0.01 for per-share EPS,
sub-cent for the deal-level identities and the dimensionless ownership sum).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.interfaces import (
    CombinationResult,
    DealResult,
    MergerModelBundle,
    StatementSet,
)
from src.schema import LineItem


@dataclass
class InvariantResult:
    name: str
    residuals: list[float] = field(default_factory=list)
    tol: float = 1.0

    @property
    def ok(self) -> bool:
        return all(abs(r) <= self.tol for r in self.residuals)

    @property
    def max_abs(self) -> float:
        return max((abs(r) for r in self.residuals), default=0.0)


@dataclass
class InvariantReport:
    results: list[InvariantResult]

    @property
    def passed(self) -> bool:
        return all(r.ok for r in self.results)

    def summary(self) -> str:
        parts = [
            f"{r.name}: {'OK' if r.ok else 'FAIL'} (max |resid| {r.max_abs:.4g})"
            for r in self.results
        ]
        return "Deal invariants — " + "; ".join(parts)


def _v(x: float | None) -> float:
    return 0.0 if x is None else x


# --------------------------------------------------------------------------- #
# Deal-level identities
# --------------------------------------------------------------------------- #
def check_sources_equal_uses(deal: DealResult, tol: float = 0.01) -> InvariantResult:
    """Total sources − total uses. The deal engine plugs the residual to a
    named line, so this must be ~0 by construction; a non-zero residual means
    the plug drifted."""
    su = deal.sources_and_uses
    return InvariantResult("sources_equal_uses", [su.total_sources - su.total_uses], tol)


def check_goodwill_ties(deal: DealResult, tol: float = 0.01) -> InvariantResult:
    """Goodwill − (equity purchase price − net identifiable assets). Goodwill is
    the PPA plug, so the walk must close exactly."""
    ppa = deal.ppa
    residual = ppa.goodwill - (ppa.equity_purchase_price - ppa.net_identifiable_assets)
    return InvariantResult("goodwill_ties", [residual], tol)


# --------------------------------------------------------------------------- #
# Pro forma balance sheet
# --------------------------------------------------------------------------- #
def check_pro_forma_balance_sheet(
    stmts: StatementSet, *, label: str = "", tol: float = 1.0
) -> InvariantResult:
    """Assets − (Liabilities + Equity) for every pro forma period. The pro forma
    statements carry no historical columns (``n_hist == 0``), so every column is
    checked. Honest-unknown lines contribute 0 (a period missing all three
    totals yields a 0 residual and is not a false failure)."""
    ta = stmts.series(LineItem.TOTAL_ASSETS)
    tl = stmts.series(LineItem.TOTAL_LIABILITIES)
    te = stmts.series(LineItem.TOTAL_EQUITY)
    residuals = [_v(ta[i]) - (_v(tl[i]) + _v(te[i])) for i in range(len(stmts.periods))]
    name = "pro_forma_balance_sheet" + (f"[{label}]" if label else "")
    return InvariantResult(name, residuals, tol)


# --------------------------------------------------------------------------- #
# EPS bridge recompute
# --------------------------------------------------------------------------- #
def check_eps_bridge_recompute(
    combo: CombinationResult, tax_rate: float = 0.0, *, label: str = "", tol: float = 0.01
) -> InvariantResult:
    """Independently reassemble pro forma net income from each bridge year's own
    components and confirm it reproduces the reported pro forma EPS to the cent.

    All four adjustment legs are stored after-tax (per the ``EPSBridge``
    contract), so this is a pure additive walk; ``tax_rate`` is retained for
    signature stability but not needed here. The residual is on EPS (recomputed
    NI / pro forma shares − reported EPS)."""
    del tax_rate  # legs are already after-tax; kept only for a stable signature
    residuals: list[float] = []
    for b in combo.eps_bridge:
        recomputed_ni = (
            b.acquirer_standalone_ni
            + b.target_standalone_ni
            - b.incremental_interest_aftertax
            - b.foregone_interest_aftertax
            - b.incremental_da_aftertax
            + b.synergies_aftertax
        )
        recomputed_eps = recomputed_ni / b.pro_forma_shares if b.pro_forma_shares else 0.0
        residuals.append(recomputed_eps - b.pro_forma_eps)
    name = "eps_bridge_recompute" + (f"[{label}]" if label else "")
    return InvariantResult(name, residuals, tol)


# --------------------------------------------------------------------------- #
# Contribution / ownership
# --------------------------------------------------------------------------- #
def check_contribution_ties(
    combo: CombinationResult, *, label: str = "", tol: float = 1e-9
) -> InvariantResult:
    """Pro forma ownership percentages sum to 1.0."""
    c = combo.contribution
    residual = (c.acquirer_ownership_pct + c.target_ownership_pct) - 1.0
    name = "contribution_ties" + (f"[{label}]" if label else "")
    return InvariantResult(name, [residual], tol)


# --------------------------------------------------------------------------- #
# Synergy phase-in
# --------------------------------------------------------------------------- #
def check_synergy_phase_in(
    combo: CombinationResult, tax_rate: float, *, label: str = "", tol: float = 0.01
) -> InvariantResult:
    """The realized (after-tax) synergy in each bridge year equals the case's
    phased-in run-rate, and the ramp reaches the full run-rate at steady state.

    Residuals: one per projected year (bridge synergy − run_rate × phase_in ×
    (1−t)), plus one steady-state check that ``realized`` beyond the ramp equals
    the run-rate (the ``SynergyCase.realized`` contract — "ramps to run-rate")."""
    case = combo.synergy_case
    residuals: list[float] = []
    for j, b in enumerate(combo.eps_bridge):
        expected_aftertax = case.run_rate_annual * case.phase_in[j] * (1.0 - tax_rate)
        residuals.append(b.synergies_aftertax - expected_aftertax)
    # Beyond the ramp the realized (pre-tax) synergy is the steady-state run-rate.
    residuals.append(case.realized(len(case.phase_in)) - case.run_rate_annual)
    name = "synergy_phase_in" + (f"[{label}]" if label else "")
    return InvariantResult(name, residuals, tol)


# --------------------------------------------------------------------------- #
# Runner
# --------------------------------------------------------------------------- #
def run_all(bundle: MergerModelBundle) -> InvariantReport:
    """Run every deal invariant across the bundle: the deal-level identities
    once, and the combination-level checks for each synergy case."""
    tax = bundle.deal_assumptions.marginal_tax_rate
    results: list[InvariantResult] = [
        check_sources_equal_uses(bundle.deal),
        check_goodwill_ties(bundle.deal),
    ]
    for combo in bundle.combinations:
        label = combo.synergy_case.name
        results.append(check_pro_forma_balance_sheet(combo.proforma_statements, label=label))
        results.append(check_eps_bridge_recompute(combo, tax, label=label))
        results.append(check_contribution_ties(combo, label=label))
        results.append(check_synergy_phase_in(combo, tax, label=label))
    return InvariantReport(results=results)
