"""Golden, hand-computed tests for the deal engine.

Every asserted number is worked out by hand in the docstring/comments so the
test is a check on the arithmetic, not a mirror of the implementation. No
sibling engine modules are imported — target book figures are supplied by hand.
"""

from __future__ import annotations

from datetime import date

import pytest
from src.deal import DealEngineImpl
from src.interfaces import DealAssumptions
from src.schema import ConsiderationType, DealTerms, DocProvenance, SourcedValue


def _doc() -> DocProvenance:
    return DocProvenance(
        accession="0001013462-24-000123",
        form="DEFM14A",
        filed=date(2024, 6, 1),
        section="The Merger — Merger Consideration",
        quote="$197.00 in cash and 0.3450 shares of Synopsys common stock",
    )


def _sv(value: float | None, unit: str = "USD", label: str = "") -> SourcedValue:
    return SourcedValue(value=value, provenance=_doc(), unit=unit, label=label)


# Shared clean-number shape modeled on the SNPS/ANSS mixed deal. The reference
# acquirer price (500.00) and premium-reference price (295.60) are picked to make
# the golden arithmetic exact; they are test fixtures, not disclosed facts.
CASH_PER_SHARE = 197.00
EXCHANGE_RATIO = 0.3450
REFERENCE_PRICE = 500.00
PREMIUM_REF = 295.60
TARGET_SHARES = 87_000_000.0


def _mixed_terms() -> DealTerms:
    return DealTerms(
        acquirer_ticker="SNPS",
        target_ticker="ANSS",
        acquirer_name="Synopsys, Inc.",
        target_name="ANSYS, Inc.",
        announce_date=date(2024, 1, 16),
        close_date=None,
        consideration_type=ConsiderationType.MIXED,
        cash_per_share=_sv(CASH_PER_SHARE, "USD/share"),
        exchange_ratio=_sv(EXCHANGE_RATIO, "ratio"),
        reference_acquirer_price=_sv(REFERENCE_PRICE, "USD/share"),
        premium_reference_price=_sv(PREMIUM_REF, "USD/share"),
        target_shares_outstanding=_sv(TARGET_SHARES, "shares"),
    )


# --------------------------------------------------------------------------- #
# 1. Consideration — the mixed SNPS/ANSS shape.
# --------------------------------------------------------------------------- #
def test_mixed_consideration_golden():
    """cash 197.00 + 0.3450 x 500.00 = 197.00 + 172.50 = 369.50 per share.
    x 87,000,000 shares:
      aggregate cash  = 197.00 x 87e6 = 17,139,000,000
      aggregate stock = 172.50 x 87e6 = 15,007,500,000
      equity purchase = 32,146,500,000
      new shares      = 0.3450 x 87e6 = 30,015,000
      premium         = 369.50 / 295.60 - 1 = 0.25 (295.60 x 1.25 = 369.50)"""
    result = DealEngineImpl().build(_mixed_terms(), DealAssumptions())
    c = result.consideration

    assert c.cash_per_share == pytest.approx(197.00)
    assert c.stock_per_share_value == pytest.approx(172.50)
    assert c.total_per_share == pytest.approx(369.50)
    assert c.target_shares == pytest.approx(87_000_000.0)
    assert c.aggregate_cash == pytest.approx(17_139_000_000.0)
    assert c.aggregate_stock_value == pytest.approx(15_007_500_000.0)
    assert c.equity_purchase_price == pytest.approx(32_146_500_000.0)
    assert c.new_shares_issued == pytest.approx(30_015_000.0)
    assert c.exchange_ratio == pytest.approx(0.3450)
    assert c.implied_premium_pct == pytest.approx(0.25)


def test_all_cash_consideration_golden():
    """All-cash: exchange ratio 0 -> no stock leg, no new shares.
    total = cash = 200.00; premium 200/160 - 1 = 0.25."""
    terms = DealTerms(
        acquirer_ticker="A",
        target_ticker="T",
        acquirer_name="A",
        target_name="T",
        announce_date=date(2024, 1, 1),
        close_date=None,
        consideration_type=ConsiderationType.CASH,
        cash_per_share=_sv(200.00, "USD/share"),
        premium_reference_price=_sv(160.00, "USD/share"),
        target_shares_outstanding=_sv(50_000_000.0, "shares"),
    )
    c = DealEngineImpl().build(terms, DealAssumptions()).consideration
    assert c.stock_per_share_value == 0.0
    assert c.total_per_share == pytest.approx(200.00)
    assert c.aggregate_stock_value == 0.0
    assert c.new_shares_issued == 0.0
    assert c.equity_purchase_price == pytest.approx(10_000_000_000.0)  # 200 x 50e6
    assert c.implied_premium_pct == pytest.approx(0.25)


def test_all_stock_consideration_golden():
    """All-stock: cash 0. 0.5 x 400.00 = 200.00 per share; new shares = 0.5 x 40e6."""
    terms = DealTerms(
        acquirer_ticker="A",
        target_ticker="T",
        acquirer_name="A",
        target_name="T",
        announce_date=date(2024, 1, 1),
        close_date=None,
        consideration_type=ConsiderationType.STOCK,
        exchange_ratio=_sv(0.50, "ratio"),
        reference_acquirer_price=_sv(400.00, "USD/share"),
        target_shares_outstanding=_sv(40_000_000.0, "shares"),
    )
    c = DealEngineImpl().build(terms, DealAssumptions()).consideration
    assert c.cash_per_share == 0.0
    assert c.aggregate_cash == 0.0
    assert c.stock_per_share_value == pytest.approx(200.00)
    assert c.total_per_share == pytest.approx(200.00)
    assert c.new_shares_issued == pytest.approx(20_000_000.0)
    assert c.equity_purchase_price == pytest.approx(8_000_000_000.0)  # 200 x 40e6
    assert c.implied_premium_pct is None  # no premium reference disclosed


# --------------------------------------------------------------------------- #
# 2. Sources & uses — must balance in every case (plug both directions).
# --------------------------------------------------------------------------- #
def test_mixed_sources_and_uses_balances_positive_plug():
    """Under-funded -> residual plugs to additional_cash on the sources side.
    sources pre-plug = 16.000e9 debt + 1.000e9 cash + 15.0075e9 stock = 32.0075e9
    uses    pre-plug = 32.1465e9 EPP + 0.100e9 + 0.050e9 fees        = 32.2965e9
    residual = uses - sources = 0.289e9 -> additional_cash = 289,000,000."""
    assumptions = DealAssumptions(
        new_debt=16_000_000_000.0,
        cash_on_hand_used=1_000_000_000.0,
        advisory_fees=100_000_000.0,
        financing_fees=50_000_000.0,
    )
    su = DealEngineImpl().build(_mixed_terms(), assumptions).sources_and_uses
    assert su.sources["stock_issued"] == pytest.approx(15_007_500_000.0)
    assert su.sources["additional_cash"] == pytest.approx(289_000_000.0)
    assert "excess_cash_retained" not in su.uses
    assert su.total_sources == pytest.approx(32_296_500_000.0)
    assert su.total_uses == pytest.approx(32_296_500_000.0)
    assert su.balances()


def test_sources_and_uses_balances_negative_plug():
    """Over-funded -> residual plugs to excess_cash_retained on the uses side.
    sources = 20e9 debt + 15.0075e9 stock = 35.0075e9
    uses    = 32.1465e9 EPP + 0.150e9 fees = 32.2965e9
    residual = uses - sources = -2.711e9 -> excess_cash_retained = 2,711,000,000."""
    assumptions = DealAssumptions(
        new_debt=20_000_000_000.0,
        advisory_fees=100_000_000.0,
        financing_fees=50_000_000.0,
    )
    su = DealEngineImpl().build(_mixed_terms(), assumptions).sources_and_uses
    assert su.uses["excess_cash_retained"] == pytest.approx(2_711_000_000.0)
    assert "additional_cash" not in su.sources
    assert su.balances()


def test_sources_and_uses_with_refinanced_target_debt():
    """Refinanced target debt is a use; still balances via the plug."""
    su = (
        DealEngineImpl()
        .build(
            _mixed_terms(),
            DealAssumptions(new_debt=10_000_000_000.0),
            refinanced_target_debt=500_000_000.0,
        )
        .sources_and_uses
    )
    assert su.uses["refinance_target_debt"] == pytest.approx(500_000_000.0)
    assert su.balances()


def test_all_cash_sources_and_uses_balances():
    """All-cash deal: no stock source; funded by debt + cash + plug."""
    terms = DealTerms(
        acquirer_ticker="A",
        target_ticker="T",
        acquirer_name="A",
        target_name="T",
        announce_date=date(2024, 1, 1),
        close_date=None,
        consideration_type=ConsiderationType.CASH,
        cash_per_share=_sv(200.00, "USD/share"),
        target_shares_outstanding=_sv(50_000_000.0, "shares"),
    )
    su = (
        DealEngineImpl()
        .build(terms, DealAssumptions(new_debt=6_000_000_000.0, cash_on_hand_used=4_000_000_000.0))
        .sources_and_uses
    )
    assert su.sources["stock_issued"] == 0.0
    assert su.balances()


# --------------------------------------------------------------------------- #
# 3. Purchase price accounting -> goodwill (the plug) + incremental D&A.
# --------------------------------------------------------------------------- #
def test_ppa_goodwill_golden_with_dtl():
    """Equity purchase 1,000; target book equity 600, existing GW 100 (written off).
      identifiable net assets at book = 600 - 100          = 500
      DTL = 0.25 x (200 intangible + 50 PP&E step-up)      =  62.5
      net identifiable = 500 + 200 + 50 - 62.5             = 687.5
      goodwill = 1,000 - 687.5                             = 312.5
    Incremental D&A: 200/10 + 50/5 = 20 + 10 = 30."""
    assumptions = DealAssumptions(
        intangible_step_up=200.0,
        intangible_useful_life_years=10.0,
        ppe_step_up=50.0,
        ppe_useful_life_years=5.0,
        deferred_tax_rate=0.25,
        target_existing_goodwill_written_off=True,
    )
    # Feed a hand-set equity purchase price via a tiny cash-only deal (1 share).
    terms = DealTerms(
        acquirer_ticker="A",
        target_ticker="T",
        acquirer_name="A",
        target_name="T",
        announce_date=date(2024, 1, 1),
        close_date=None,
        consideration_type=ConsiderationType.CASH,
        cash_per_share=_sv(1000.0, "USD/share"),
        target_shares_outstanding=_sv(1.0, "shares"),
    )
    result = DealEngineImpl().build(
        terms,
        assumptions,
        target_book_equity=600.0,
        target_existing_goodwill=100.0,
    )
    ppa = result.ppa
    assert ppa.equity_purchase_price == pytest.approx(1000.0)
    assert ppa.identifiable_net_assets_at_book == pytest.approx(500.0)
    assert ppa.deferred_tax_liability == pytest.approx(62.5)
    assert ppa.net_identifiable_assets == pytest.approx(687.5)
    assert ppa.goodwill == pytest.approx(312.5)
    assert ppa.ties()
    assert result.incremental_da_annual == pytest.approx(30.0)


def test_ppa_goodwill_existing_gw_retained():
    """When existing goodwill is NOT written off, it stays inside identifiable
    net assets, lowering goodwill: net identifiable = 600 + 200 + 50 - 62.5 = 787.5;
    goodwill = 1,000 - 787.5 = 212.5."""
    assumptions = DealAssumptions(
        intangible_step_up=200.0,
        ppe_step_up=50.0,
        deferred_tax_rate=0.25,
        target_existing_goodwill_written_off=False,
    )
    terms = DealTerms(
        acquirer_ticker="A",
        target_ticker="T",
        acquirer_name="A",
        target_name="T",
        announce_date=date(2024, 1, 1),
        close_date=None,
        consideration_type=ConsiderationType.CASH,
        cash_per_share=_sv(1000.0, "USD/share"),
        target_shares_outstanding=_sv(1.0, "shares"),
    )
    ppa = (
        DealEngineImpl()
        .build(terms, assumptions, target_book_equity=600.0, target_existing_goodwill=100.0)
        .ppa
    )
    assert ppa.identifiable_net_assets_at_book == pytest.approx(600.0)
    assert ppa.net_identifiable_assets == pytest.approx(787.5)
    assert ppa.goodwill == pytest.approx(212.5)
    assert ppa.ties()


def test_incremental_da_zero_useful_life_is_zero():
    """A step-up with no useful life contributes 0 D&A (honest unknown, not a
    divide-by-zero)."""
    assumptions = DealAssumptions(
        intangible_step_up=200.0,
        intangible_useful_life_years=0.0,
        ppe_step_up=50.0,
        ppe_useful_life_years=0.0,
    )
    result = DealEngineImpl().build(_mixed_terms(), assumptions)
    assert result.incremental_da_annual == 0.0
