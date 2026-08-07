"""Combination engine — pro forma statements, EPS bridge, accretion/dilution.

Implements the ``CombinationEngine`` protocol (src/interfaces.py): given both
standalone ``StatementSet``s, the ``DealResult`` (consideration, S&U, purchase
price accounting), our ``DealAssumptions``, and one ``SynergyCase``, it produces
a ``CombinationResult`` for one synergy scenario across the projection horizon.

Tax convention (deliberate — matches the frozen EPSBridge contract):
    We use the INCREMENTAL accretion/dilution build. Each company's standalone
    net income is preserved as reported (so standalone EPS is the true reported
    EPS and the classic P/E intuition holds); only the *deal adjustments* are
    taxed, at ``deal_assumptions.marginal_tax_rate``:

        pro forma NI = acquirer_standalone_ni + target_standalone_ni
                       − incremental_interest_expense × (1 − t)   [new-debt coupon]
                       − foregone_interest_income   × (1 − t)   [yield on cash used]
                       − incremental_da_aftertax                 [step-up D&A, after tax]
                       + synergies_aftertax                      [realized synergies, after tax]

    This is the only build consistent with the EPSBridge fields (separate
    standalone NIs + after-tax adjustment items that sum to pro forma NI): a
    "tax the whole combined pretax at the marginal rate" build cannot populate
    those fields without an unexplained tax-restatement plug. Interest legs are
    stored pre-tax (per the field names); D&A and synergies are stored after
    tax (per the field comments). The pro forma income statement's PRETAX /
    TAX / NET_INCOME lines are built to reconcile exactly to this same NI.

Pro forma balance sheet: the combined (acquirer + target) balance sheet with the
purchase-accounting adjustments layered on at the deal date and carried across
every projected period — new goodwill (target's existing goodwill written off),
asset step-ups, the deferred-tax liability they create, new acquisition debt,
the cash drawn down, and target equity eliminated and replaced by the equity
issued to target holders (less expensed fees). It balances every period whenever
sources = uses and the target's book equity ties to its reported total equity.

Signs follow the contract in src/interfaces.py: values are raw USD; interest
expense is stored positive and subtracted; the incremental-D&A and interest
adjustments are positive magnitudes subtracted from income.
"""

from __future__ import annotations

from src.interfaces import (
    CombinationResult,
    ContributionAnalysis,
    DealAssumptions,
    DealResult,
    EPSBridge,
    StatementSet,
    SynergyCase,
)
from src.schema import LineItem, Period


def _v(series_value: float | None) -> float:
    """A single optional statement value as a float, honest-missing → 0.0.

    Used only where summing/adjusting a line whose economic combined value is
    "present + absent" (the absent side contributes nothing). Callers that must
    distinguish a genuine unknown check the raw series first (see _combined_row).
    """
    return 0.0 if series_value is None else float(series_value)


def _at(statements: StatementSet, li: LineItem, idx: int) -> float | None:
    """Raw value of ``li`` at absolute period ``idx`` (None = honest unknown)."""
    series = statements.series(li)
    if idx < 0 or idx >= len(series):
        return None
    return series[idx]


class CombinationEngine:
    """Assembles pro forma statements, the EPS bridge, and accretion/dilution.

    Concrete implementation of the ``CombinationEngine`` protocol.
    """

    def combine(
        self,
        acquirer: StatementSet,
        target: StatementSet,
        deal: DealResult,
        deal_assumptions: DealAssumptions,
        synergies: SynergyCase,
    ) -> CombinationResult:
        t = deal_assumptions.marginal_tax_rate
        one_minus_t = 1.0 - t

        # Deal-level constants (same every projected year).
        incr_interest = deal_assumptions.new_debt * deal_assumptions.new_debt_rate
        foregone_income = deal_assumptions.cash_on_hand_used * deal_assumptions.foregone_cash_yield
        incr_da_pretax = deal.incremental_da_annual
        incr_da_aftertax = incr_da_pretax * one_minus_t
        new_shares = deal.consideration.new_shares_issued

        # Projected period columns come from the acquirer; pair with the target
        # by projection index (both standalone models share the horizon).
        proj_periods: list[Period] = acquirer.periods[acquirer.n_hist :]
        n_proj = min(len(proj_periods), len(target.periods) - target.n_hist)

        eps_bridge: list[EPSBridge] = []
        pf_rows: dict[LineItem, list[float | None]] = {}
        pf_periods: list[Period] = []

        for j in range(n_proj):
            period = proj_periods[j]
            pf_periods.append(period)
            a_idx = acquirer.n_hist + j
            t_idx = target.n_hist + j

            # --- Income statement -------------------------------------------------
            acq_ni = _v(_at(acquirer, LineItem.NET_INCOME, a_idx))
            tgt_ni = _v(_at(target, LineItem.NET_INCOME, t_idx))

            synergies_pretax = synergies.realized(j)
            synergies_aftertax = synergies_pretax * one_minus_t

            pro_forma_ni = (
                acq_ni
                + tgt_ni
                - incr_interest * one_minus_t
                - foregone_income * one_minus_t
                - incr_da_aftertax
                + synergies_aftertax
            )

            acq_shares = _v(_at(acquirer, LineItem.SHARES_DILUTED, a_idx))
            pf_shares = acq_shares + new_shares
            acq_eps = acq_ni / acq_shares if acq_shares else 0.0
            pf_eps = pro_forma_ni / pf_shares if pf_shares else 0.0

            eps_bridge.append(
                EPSBridge(
                    year=period,
                    acquirer_standalone_ni=acq_ni,
                    target_standalone_ni=tgt_ni,
                    incremental_interest_expense=incr_interest,
                    foregone_interest_income=foregone_income,
                    incremental_da_aftertax=incr_da_aftertax,
                    synergies_aftertax=synergies_aftertax,
                    pro_forma_net_income=pro_forma_ni,
                    acquirer_standalone_shares=acq_shares,
                    new_shares_issued=new_shares,
                    pro_forma_shares=pf_shares,
                    acquirer_standalone_eps=acq_eps,
                    pro_forma_eps=pf_eps,
                )
            )

            self._fill_income_statement(
                pf_rows,
                acquirer,
                target,
                a_idx,
                t_idx,
                incr_interest=incr_interest,
                foregone_income=foregone_income,
                incr_da_pretax=incr_da_pretax,
                synergies_pretax=synergies_pretax,
                tax_rate=t,
                pro_forma_ni=pro_forma_ni,
                pf_shares=pf_shares,
                pf_eps=pf_eps,
            )
            self._fill_balance_sheet(
                pf_rows, acquirer, target, a_idx, t_idx, deal, deal_assumptions
            )

        proforma_statements = StatementSet(periods=pf_periods, rows=pf_rows, n_hist=0)
        contribution = self._contribution(acquirer, target, deal, n_proj)

        return CombinationResult(
            synergy_case=synergies,
            proforma_statements=proforma_statements,
            eps_bridge=eps_bridge,
            contribution=contribution,
        )

    # ------------------------------------------------------------------ #
    # income statement
    # ------------------------------------------------------------------ #
    def _fill_income_statement(
        self,
        pf_rows: dict[LineItem, list[float | None]],
        acquirer: StatementSet,
        target: StatementSet,
        a_idx: int,
        t_idx: int,
        *,
        incr_interest: float,
        foregone_income: float,
        incr_da_pretax: float,
        synergies_pretax: float,
        tax_rate: float,
        pro_forma_ni: float,
        pf_shares: float,
        pf_eps: float,
    ) -> None:
        """Append one projected year of pro forma income-statement lines.

        Lines are built to reconcile to ``pro_forma_ni``: standalone pretax and
        tax are summed, the deal adjustments are added pre-tax to pretax and
        taxed at the marginal rate, so PRETAX − TAX == pro forma NI exactly. A
        line whose inputs are all honest-unknown stays None.
        """

        def combined(li: LineItem) -> float | None:
            return self._combined_row(acquirer, target, li, a_idx, t_idx)

        # Combined operating lines with the deal adjustments applied pre-tax.
        adj_pretax = -incr_interest - foregone_income - incr_da_pretax + synergies_pretax

        self._push(pf_rows, LineItem.REVENUE, combined(LineItem.REVENUE))

        oi = combined(LineItem.OPERATING_INCOME)
        # step-up D&A and realized synergies hit operating income.
        oi_pf = None if oi is None else oi - incr_da_pretax + synergies_pretax
        self._push(pf_rows, LineItem.OPERATING_INCOME, oi_pf)

        int_exp = combined(LineItem.INTEREST_EXPENSE)
        self._push(
            pf_rows,
            LineItem.INTEREST_EXPENSE,
            None if int_exp is None else int_exp + incr_interest,
        )
        int_inc = combined(LineItem.INTEREST_INCOME)
        self._push(
            pf_rows,
            LineItem.INTEREST_INCOME,
            None if int_inc is None else int_inc - foregone_income,
        )
        da = combined(LineItem.DEP_AMORT)
        self._push(pf_rows, LineItem.DEP_AMORT, None if da is None else da + incr_da_pretax)

        pretax = combined(LineItem.PRETAX_INCOME)
        tax = combined(LineItem.INCOME_TAX_EXPENSE)
        if pretax is not None:
            pf_pretax = pretax + adj_pretax
            self._push(pf_rows, LineItem.PRETAX_INCOME, pf_pretax)
            if tax is not None:
                self._push(
                    pf_rows,
                    LineItem.INCOME_TAX_EXPENSE,
                    tax + adj_pretax * tax_rate,
                )
        else:
            self._push(pf_rows, LineItem.PRETAX_INCOME, None)
            self._push(pf_rows, LineItem.INCOME_TAX_EXPENSE, None)

        self._push(pf_rows, LineItem.NET_INCOME, pro_forma_ni)
        self._push(pf_rows, LineItem.SHARES_DILUTED, pf_shares)
        self._push(pf_rows, LineItem.EPS_DILUTED, pf_eps)

    # ------------------------------------------------------------------ #
    # balance sheet
    # ------------------------------------------------------------------ #
    def _fill_balance_sheet(
        self,
        pf_rows: dict[LineItem, list[float | None]],
        acquirer: StatementSet,
        target: StatementSet,
        a_idx: int,
        t_idx: int,
        deal: DealResult,
        da: DealAssumptions,
    ) -> None:
        """Append one projected year of pro forma balance-sheet lines.

        Purchase-accounting adjustments (constant deal-date entries) are layered
        onto the combined balance sheet. The three totals are recomputed via the
        same deltas so A = L + E holds whenever S&U balances and the target's
        book equity ties to its reported total equity.
        """
        ppa = deal.ppa

        def combined(li: LineItem) -> float | None:
            return self._combined_row(acquirer, target, li, a_idx, t_idx)

        def tgt(li: LineItem) -> float:
            return _v(_at(target, li, t_idx))

        agg_stock = deal.consideration.aggregate_stock_value
        fees = da.advisory_fees + da.financing_fees
        target_gw_written_off = (
            ppa.target_existing_goodwill if da.target_existing_goodwill_written_off else 0.0
        )

        # --- Assets ---
        cash = combined(LineItem.CASH)
        self._push(pf_rows, LineItem.CASH, None if cash is None else cash - da.cash_on_hand_used)

        gw = combined(LineItem.GOODWILL)
        # Replace target's written-off goodwill with the new deal goodwill.
        self._push(
            pf_rows,
            LineItem.GOODWILL,
            None if gw is None else gw - target_gw_written_off + ppa.goodwill,
        )
        intang = combined(LineItem.INTANGIBLES)
        self._push(
            pf_rows,
            LineItem.INTANGIBLES,
            None if intang is None else intang + ppa.intangible_step_up,
        )
        ppe = combined(LineItem.PPE_NET)
        self._push(pf_rows, LineItem.PPE_NET, None if ppe is None else ppe + ppa.ppe_step_up)

        # --- Liabilities ---
        ltd = combined(LineItem.LONG_TERM_DEBT)
        self._push(pf_rows, LineItem.LONG_TERM_DEBT, None if ltd is None else ltd + da.new_debt)
        dtl = combined(LineItem.DEFERRED_TAX_LIABILITIES)
        self._push(
            pf_rows,
            LineItem.DEFERRED_TAX_LIABILITIES,
            None if dtl is None else dtl + ppa.deferred_tax_liability,
        )

        # --- Equity: eliminate ALL target equity, add issuance, expense fees ---
        cs = combined(LineItem.COMMON_STOCK)
        self._push(
            pf_rows,
            LineItem.COMMON_STOCK,
            None if cs is None else cs - tgt(LineItem.COMMON_STOCK) + agg_stock,
        )
        re = combined(LineItem.RETAINED_EARNINGS)
        self._push(
            pf_rows,
            LineItem.RETAINED_EARNINGS,
            None if re is None else re - tgt(LineItem.RETAINED_EARNINGS) - fees,
        )
        for li in (LineItem.TREASURY_STOCK, LineItem.AOCI):
            val = combined(li)
            self._push(pf_rows, li, None if val is None else val - tgt(li))

        # --- Totals (recomputed via deltas so the sheet balances) ---
        asset_delta = (
            -da.cash_on_hand_used
            + (ppa.goodwill - target_gw_written_off)
            + ppa.intangible_step_up
            + ppa.ppe_step_up
        )
        liab_delta = da.new_debt + ppa.deferred_tax_liability
        equity_delta = -tgt(LineItem.TOTAL_EQUITY) + agg_stock - fees

        ta = combined(LineItem.TOTAL_ASSETS)
        self._push(pf_rows, LineItem.TOTAL_ASSETS, None if ta is None else ta + asset_delta)
        tl = combined(LineItem.TOTAL_LIABILITIES)
        self._push(pf_rows, LineItem.TOTAL_LIABILITIES, None if tl is None else tl + liab_delta)
        te = combined(LineItem.TOTAL_EQUITY)
        self._push(pf_rows, LineItem.TOTAL_EQUITY, None if te is None else te + equity_delta)

    # ------------------------------------------------------------------ #
    # contribution analysis
    # ------------------------------------------------------------------ #
    def _contribution(
        self, acquirer: StatementSet, target: StatementSet, deal: DealResult, n_proj: int
    ) -> ContributionAnalysis:
        """Each party's revenue/EBITDA/net income (first projected year) and its
        pro forma ownership of the combined entity."""
        a_idx = acquirer.n_hist if n_proj else max(acquirer.n_hist - 1, 0)
        t_idx = target.n_hist if n_proj else max(target.n_hist - 1, 0)

        def ebitda(statements: StatementSet, idx: int) -> float:
            return _v(_at(statements, LineItem.OPERATING_INCOME, idx)) + _v(
                _at(statements, LineItem.DEP_AMORT, idx)
            )

        acq_shares = _v(_at(acquirer, LineItem.SHARES_DILUTED, a_idx))
        new_shares = deal.consideration.new_shares_issued
        pf_shares = acq_shares + new_shares
        acq_own = acq_shares / pf_shares if pf_shares else 0.0
        tgt_own = new_shares / pf_shares if pf_shares else 0.0

        return ContributionAnalysis(
            acquirer_revenue=_v(_at(acquirer, LineItem.REVENUE, a_idx)),
            target_revenue=_v(_at(target, LineItem.REVENUE, t_idx)),
            acquirer_ebitda=ebitda(acquirer, a_idx),
            target_ebitda=ebitda(target, t_idx),
            acquirer_net_income=_v(_at(acquirer, LineItem.NET_INCOME, a_idx)),
            target_net_income=_v(_at(target, LineItem.NET_INCOME, t_idx)),
            acquirer_ownership_pct=acq_own,
            target_ownership_pct=tgt_own,
        )

    # ------------------------------------------------------------------ #
    # helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _combined_row(
        acquirer: StatementSet, target: StatementSet, li: LineItem, a_idx: int, t_idx: int
    ) -> float | None:
        """Acquirer + target for one line/period. Both honest-unknown → None;
        otherwise a present side contributes and an absent side contributes 0."""
        a = _at(acquirer, li, a_idx)
        b = _at(target, li, t_idx)
        if a is None and b is None:
            return None
        return _v(a) + _v(b)

    @staticmethod
    def _push(
        pf_rows: dict[LineItem, list[float | None]], li: LineItem, value: float | None
    ) -> None:
        pf_rows.setdefault(li, []).append(value)
