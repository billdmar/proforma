"""The deal engine: consideration, sources & uses, purchase price accounting.

Implements the ``DealEngine`` protocol from ``src.interfaces``. It turns the
disclosed ``DealTerms`` plus OUR ``DealAssumptions`` into a ``DealResult``:

1. **Consideration** — per-share cash + stock legs grossed up to aggregates,
   implied premium vs the disclosed premium-reference price, and the new-share
   count issued for the stock leg.
2. **Sources & uses** — the cash raised (new debt + balance-sheet cash) plus the
   stock issued must fund the equity purchase price, any refinanced target debt,
   and fees. If the disclosed/assumed financing does not balance, the residual is
   plugged to a clearly-named line so ``SourcesAndUses.balances()`` holds.
3. **Purchase price accounting** — equity purchase price less the target's
   identifiable net assets (book equity, optionally net of its existing goodwill,
   stepped up for intangibles/PP&E, less the deferred-tax liability those
   step-ups create) leaves goodwill as the plug.
4. **Incremental annual D&A** — straight-line amortization/depreciation of the
   step-ups, which feeds the pro forma income statement built downstream.

Deal math signs & conventions follow ``src.interfaces`` (raw USD magnitudes;
goodwill = equity purchase price − net identifiable assets; sources = uses).

The target book figures the PPA needs (book equity, existing goodwill) and any
refinanced target debt are NOT part of the frozen ``DealAssumptions`` contract,
so ``build`` accepts them as optional keyword parameters (defaulting to 0.0).
The pro forma builder supplies them from the target's balance sheet; tests pass
them by hand. This keeps the deal engine buildable in parallel with the models.
"""

from __future__ import annotations

from src.interfaces import (
    Consideration,
    DealAssumptions,
    DealResult,
    PurchasePriceAllocation,
    SourcesAndUses,
)
from src.schema import DealTerms, SourcedValue


def _val(sv: SourcedValue | None) -> float | None:
    """Disclosed scalar or None (honest unknown / absent leg)."""
    return sv.value if sv is not None else None


def _val0(sv: SourcedValue | None) -> float:
    """Disclosed scalar coerced to 0.0 when absent — used for legs that are
    genuinely zero for a given consideration type (e.g. exchange ratio in an
    all-cash deal), never to paper over a missing required figure."""
    v = _val(sv)
    return v if v is not None else 0.0


class DealEngineImpl:
    """Consideration + sources & uses + purchase price accounting."""

    def build(
        self,
        terms: DealTerms,
        assumptions: DealAssumptions,
        *,
        target_book_equity: float = 0.0,
        target_existing_goodwill: float = 0.0,
        refinanced_target_debt: float = 0.0,
    ) -> DealResult:
        consideration = self._consideration(terms)
        sources_and_uses = self._sources_and_uses(
            consideration, assumptions, refinanced_target_debt
        )
        ppa = self._ppa(
            consideration.equity_purchase_price,
            assumptions,
            target_book_equity,
            target_existing_goodwill,
        )
        incremental_da_annual = self._incremental_da(assumptions)
        return DealResult(
            consideration=consideration,
            sources_and_uses=sources_and_uses,
            ppa=ppa,
            incremental_da_annual=incremental_da_annual,
        )

    # --- 1. Consideration -------------------------------------------------- #
    def _consideration(self, terms: DealTerms) -> Consideration:
        cash_per_share = _val0(terms.cash_per_share)
        exchange_ratio = _val0(terms.exchange_ratio)
        reference_price = _val0(terms.reference_acquirer_price)

        stock_per_share_value = exchange_ratio * reference_price
        total_per_share = cash_per_share + stock_per_share_value
        target_shares = _val0(terms.target_shares_outstanding)

        aggregate_cash = cash_per_share * target_shares
        aggregate_stock_value = stock_per_share_value * target_shares
        equity_purchase_price = aggregate_cash + aggregate_stock_value
        new_shares_issued = exchange_ratio * target_shares

        # Implied premium vs the disclosed premium-reference price, when both the
        # reference price and a positive total consideration are available.
        premium_ref = _val(terms.premium_reference_price)
        implied_premium_pct: float | None = None
        if premium_ref is not None and premium_ref != 0.0:
            implied_premium_pct = total_per_share / premium_ref - 1.0

        return Consideration(
            cash_per_share=cash_per_share,
            stock_per_share_value=stock_per_share_value,
            total_per_share=total_per_share,
            target_shares=target_shares,
            aggregate_cash=aggregate_cash,
            aggregate_stock_value=aggregate_stock_value,
            equity_purchase_price=equity_purchase_price,
            implied_premium_pct=implied_premium_pct,
            exchange_ratio=exchange_ratio,
            new_shares_issued=new_shares_issued,
        )

    # --- 2. Sources & uses ------------------------------------------------- #
    def _sources_and_uses(
        self,
        consideration: Consideration,
        assumptions: DealAssumptions,
        refinanced_target_debt: float,
    ) -> SourcesAndUses:
        # Stock leg funds itself: shares issued to target holders are a non-cash
        # source equal to the aggregate stock value inside the purchase price.
        sources: dict[str, float] = {
            "new_debt": assumptions.new_debt,
            "cash_on_hand": assumptions.cash_on_hand_used,
            "stock_issued": consideration.aggregate_stock_value,
        }
        uses: dict[str, float] = {
            "equity_purchase_price": consideration.equity_purchase_price,
            "refinance_target_debt": refinanced_target_debt,
            "advisory_fees": assumptions.advisory_fees,
            "financing_fees": assumptions.financing_fees,
        }

        # Plug the residual so sources == uses. A positive residual (uses exceed
        # sources) means the acquirer must fund more cash than the disclosed/
        # assumed financing covers — plug it to acquirer cash on hand. A negative
        # residual (over-funded) is returned/retained as excess cash on the uses
        # side. Either way balances() holds; the plug is explicit, never silent.
        residual = sum(uses.values()) - sum(sources.values())
        if residual >= 0.0:
            sources["additional_cash"] = residual
        else:
            uses["excess_cash_retained"] = -residual

        return SourcesAndUses(sources=sources, uses=uses)

    # --- 3. Purchase price accounting -> goodwill -------------------------- #
    def _ppa(
        self,
        equity_purchase_price: float,
        assumptions: DealAssumptions,
        target_book_equity: float,
        target_existing_goodwill: float,
    ) -> PurchasePriceAllocation:
        # Existing goodwill is written off before re-allocation unless the
        # modeling choice keeps it (then it stays inside identifiable net assets).
        existing_gw_removed = (
            target_existing_goodwill if assumptions.target_existing_goodwill_written_off else 0.0
        )
        identifiable_net_assets_at_book = target_book_equity - existing_gw_removed

        intangible_step_up = assumptions.intangible_step_up
        ppe_step_up = assumptions.ppe_step_up
        deferred_tax_liability = assumptions.deferred_tax_rate * (intangible_step_up + ppe_step_up)

        net_identifiable_assets = (
            identifiable_net_assets_at_book
            + intangible_step_up
            + ppe_step_up
            - deferred_tax_liability
        )
        goodwill = equity_purchase_price - net_identifiable_assets

        return PurchasePriceAllocation(
            equity_purchase_price=equity_purchase_price,
            target_book_equity=target_book_equity,
            target_existing_goodwill=target_existing_goodwill,
            identifiable_net_assets_at_book=identifiable_net_assets_at_book,
            intangible_step_up=intangible_step_up,
            ppe_step_up=ppe_step_up,
            deferred_tax_liability=deferred_tax_liability,
            net_identifiable_assets=net_identifiable_assets,
            goodwill=goodwill,
        )

    # --- 4. Incremental annual D&A from step-ups --------------------------- #
    def _incremental_da(self, assumptions: DealAssumptions) -> float:
        # Straight-line: a step-up with no useful life contributes nothing rather
        # than dividing by zero (an honest unknown, not a fabricated charge).
        intangible = (
            assumptions.intangible_step_up / assumptions.intangible_useful_life_years
            if assumptions.intangible_useful_life_years > 0.0
            else 0.0
        )
        ppe = (
            assumptions.ppe_step_up / assumptions.ppe_useful_life_years
            if assumptions.ppe_useful_life_years > 0.0
            else 0.0
        )
        return intangible + ppe
