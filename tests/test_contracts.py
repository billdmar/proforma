"""Contract tests — exercise the frozen schema + interface dataclasses.

These lock the W0 contracts (src/schema.py, src/interfaces.py): the
NormalizedFacts restatement/accessor logic reused from thesis, and the
merger-specific deal/combination/fairness types. They also keep coverage green
before the W1 engines land. Golden values are hand-computed in the docstrings.
"""

from __future__ import annotations

from datetime import date

import pytest
from src.interfaces import (
    Consideration,
    ContributionAnalysis,
    DealAssumptions,
    DealResult,
    EPSBridge,
    FairnessDifferentialReport,
    MergerModelBundle,
    MethodologyReproduction,
    ProjectionAssumptions,
    PurchasePriceAllocation,
    SensitivityGrid,
    SensitivitySet,
    SourcesAndUses,
    StatementSet,
    SynergyCase,
)
from src.schema import (
    STATEMENT_OF,
    AdvisorMethodology,
    CompanyMeta,
    ConsiderationType,
    DealTerms,
    DocProvenance,
    Fact,
    FairnessDisclosure,
    LineItem,
    NormalizedFacts,
    Period,
    PeriodType,
    Provenance,
    SourcedRange,
    SourcedValue,
    Statement,
    Unit,
)

# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
FYE_2023 = Period(PeriodType.DURATION, end=date(2023, 12, 31), start=date(2023, 1, 1), fp="FY")
FYE_2024 = Period(PeriodType.DURATION, end=date(2024, 12, 31), start=date(2024, 1, 1), fp="FY")
BS_2023 = Period(PeriodType.INSTANT, end=date(2023, 12, 31))
BS_2024 = Period(PeriodType.INSTANT, end=date(2024, 12, 31))


def _prov(accession: str, filed: date, tag: str = "Revenues") -> Provenance:
    return Provenance(
        xbrl_tag=tag,
        taxonomy="us-gaap",
        unit=Unit.USD,
        accession=accession,
        form="10-K",
        filed=filed,
    )


def _doc(accession: str = "0001013462-24-000123", form: str = "DEFM14A") -> DocProvenance:
    return DocProvenance(
        accession=accession,
        form=form,
        filed=date(2024, 6, 1),
        section="Opinion of Financial Advisor",
        quote="$35.00 per share in cash",
    )


# --------------------------------------------------------------------------- #
# schema: Period
# --------------------------------------------------------------------------- #
def test_period_validation_and_key():
    assert FYE_2023.key == ("duration", date(2023, 1, 1), date(2023, 12, 31))
    assert BS_2023.key == ("instant", None, date(2023, 12, 31))
    with pytest.raises(ValueError):
        Period(PeriodType.DURATION, end=date(2023, 12, 31))  # missing start
    with pytest.raises(ValueError):
        Period(PeriodType.INSTANT, end=date(2023, 12, 31), start=date(2023, 1, 1))


def test_statement_of_covers_every_line_item():
    for li in LineItem:
        assert li in STATEMENT_OF
    assert STATEMENT_OF[LineItem.REVENUE] is Statement.INCOME
    assert STATEMENT_OF[LineItem.GOODWILL] is Statement.BALANCE
    assert STATEMENT_OF[LineItem.CFO] is Statement.CASHFLOW


# --------------------------------------------------------------------------- #
# schema: NormalizedFacts restatement resolution + accessors
# --------------------------------------------------------------------------- #
def test_normalized_facts_restatement_latest_wins():
    nf = NormalizedFacts(company=CompanyMeta(cik="0000883241", ticker="SNPS", name="Synopsys"))
    older = Fact(
        LineItem.REVENUE, FYE_2023, 5_000.0, _prov("0000883241-24-000001", date(2024, 2, 1))
    )
    newer = Fact(
        LineItem.REVENUE, FYE_2023, 5_050.0, _prov("0000883241-25-000001", date(2025, 2, 1))
    )
    nf.add(older)
    nf.add(newer)  # later filing wins; older recorded under superseded
    got = nf.get(LineItem.REVENUE, FYE_2023)
    assert got.value == 5_050.0
    assert len(got.superseded) == 1
    assert got.superseded[0].accession == "0000883241-24-000001"


def test_normalized_facts_out_of_order_add_resolves_same():
    nf = NormalizedFacts(company=CompanyMeta(cik="1", ticker="X", name="X"))
    newer = Fact(LineItem.REVENUE, FYE_2023, 42.0, _prov("acc-new", date(2025, 2, 1)))
    older = Fact(LineItem.REVENUE, FYE_2023, 40.0, _prov("acc-old", date(2024, 2, 1)))
    nf.add(newer)
    nf.add(older)  # older arrives second but must not overwrite
    assert nf.value(LineItem.REVENUE, FYE_2023) == 42.0


def test_normalized_facts_value_is_honest_unknown():
    nf = NormalizedFacts(company=CompanyMeta(cik="1", ticker="X", name="X"))
    assert nf.value(LineItem.REVENUE, FYE_2023) is None
    assert nf.get(LineItem.REVENUE, FYE_2023) is None


def test_normalized_facts_period_accessors_sorted():
    nf = NormalizedFacts(company=CompanyMeta(cik="1", ticker="X", name="X"))
    nf.add(Fact(LineItem.REVENUE, FYE_2024, 1.0, _prov("a", date(2025, 2, 1))))
    nf.add(Fact(LineItem.REVENUE, FYE_2023, 1.0, _prov("b", date(2024, 2, 1))))
    nf.add(Fact(LineItem.TOTAL_ASSETS, BS_2024, 1.0, _prov("a", date(2025, 2, 1), "Assets")))
    nf.add(Fact(LineItem.TOTAL_ASSETS, BS_2023, 1.0, _prov("b", date(2024, 2, 1), "Assets")))
    assert [p.end.year for p in nf.annual_periods()] == [2023, 2024]
    assert [p.end.year for p in nf.instant_periods()] == [2023, 2024]


def test_fact_key():
    f = Fact(LineItem.REVENUE, FYE_2023, 1.0, _prov("a", date(2024, 2, 1)))
    assert f.key == ("revenue", FYE_2023.key)


# --------------------------------------------------------------------------- #
# schema: merger deal-fact records with provenance
# --------------------------------------------------------------------------- #
def test_sourced_value_and_range_carry_provenance():
    sv = SourcedValue(value=35.0, provenance=_doc(), unit="USD/share", label="cash/share")
    assert sv.value == 35.0 and sv.provenance.form == "DEFM14A"
    sr = SourcedRange(low=110.46, high=257.96, provenance=_doc(), label="DCF implied range")
    assert sr.low < sr.high
    honest_unknown = SourcedValue(value=None, provenance=_doc())
    assert honest_unknown.value is None


def test_deal_terms_and_fairness_disclosure_shape():
    terms = DealTerms(
        acquirer_ticker="SNPS",
        target_ticker="ANSS",
        acquirer_name="Synopsys, Inc.",
        target_name="ANSYS, Inc.",
        announce_date=date(2024, 1, 16),
        close_date=None,
        consideration_type=ConsiderationType.MIXED,
        cash_per_share=SourcedValue(197.0, _doc(), "USD/share"),
        exchange_ratio=SourcedValue(0.345, _doc(), "ratio"),
    )
    assert terms.consideration_type is ConsiderationType.MIXED
    assert terms.cash_per_share.value == 197.0
    fd = FairnessDisclosure(
        advisor="Qatalyst Partners",
        represents="ANSS",
        methodologies=[
            AdvisorMethodology(
                method="DCF",
                implied_range=SourcedRange(300.0, 400.0, _doc()),
                assumptions={"discount_rate": SourcedRange(0.09, 0.11, _doc(), "ratio")},
            )
        ],
    )
    assert fd.methodologies[0].assumptions["discount_rate"].high == 0.11


# --------------------------------------------------------------------------- #
# interfaces: deal-engine invariants
# --------------------------------------------------------------------------- #
def test_sources_and_uses_balances():
    su = SourcesAndUses(
        sources={"new_debt": 60.0, "cash_on_hand": 20.0, "stock_issued": 20.0},
        uses={"equity_purchase_price": 95.0, "fees": 5.0},
    )
    assert su.total_sources == 100.0
    assert su.total_uses == 100.0
    assert su.balances()
    bad = SourcesAndUses(sources={"a": 100.0}, uses={"b": 99.0})
    assert not bad.balances()
    assert bad.balances(tol=2.0)


def test_ppa_goodwill_ties():
    """Goodwill is the plug: 1000 purchase − (600 book eq − 100 existing GW
    + 150 intangible step-up + 0 PP&E − 30 DTL) = 1000 − 620 = 380."""
    net_identifiable = 600.0 - 100.0 + 150.0 + 0.0 - 30.0  # 620
    ppa = PurchasePriceAllocation(
        equity_purchase_price=1000.0,
        target_book_equity=600.0,
        target_existing_goodwill=100.0,
        identifiable_net_assets_at_book=500.0,
        intangible_step_up=150.0,
        ppe_step_up=0.0,
        deferred_tax_liability=30.0,
        net_identifiable_assets=net_identifiable,
        goodwill=1000.0 - net_identifiable,
    )
    assert ppa.goodwill == 380.0
    assert ppa.ties()


# --------------------------------------------------------------------------- #
# interfaces: combination — synergy phase-in + EPS bridge accretion
# --------------------------------------------------------------------------- #
def test_synergy_case_phase_in():
    sc = SynergyCase(
        name="Management (disclosed)",
        run_rate_annual=400.0,
        phase_in=[0.25, 0.5, 1.0],
        is_disclosed=True,
    )
    assert sc.realized(0) == 100.0
    assert sc.realized(1) == 200.0
    assert sc.realized(2) == 400.0
    assert sc.realized(5) == 400.0  # steady state beyond ramp


def test_eps_bridge_accretion():
    """Standalone EPS 5.00, pro forma EPS 5.50 → +10% accretion."""
    b = EPSBridge(
        year=FYE_2024,
        acquirer_standalone_ni=500.0,
        target_standalone_ni=200.0,
        incremental_interest_aftertax=50.0,
        foregone_interest_aftertax=10.0,
        incremental_da_aftertax=30.0,
        synergies_aftertax=40.0,
        pro_forma_net_income=605.0,
        acquirer_standalone_shares=100.0,
        new_shares_issued=10.0,
        pro_forma_shares=110.0,
        acquirer_standalone_eps=5.0,
        pro_forma_eps=5.5,
    )
    assert b.accretion_dilution_pct == pytest.approx(0.10)
    zero = EPSBridge(
        year=FYE_2024,
        acquirer_standalone_ni=0,
        target_standalone_ni=0,
        incremental_interest_aftertax=0,
        foregone_interest_aftertax=0,
        incremental_da_aftertax=0,
        synergies_aftertax=0,
        pro_forma_net_income=0,
        acquirer_standalone_shares=0,
        new_shares_issued=0,
        pro_forma_shares=0,
        acquirer_standalone_eps=0.0,
        pro_forma_eps=0.0,
    )
    assert zero.accretion_dilution_pct is None


def test_fairness_differential_mean_overlap():
    rep = FairnessDifferentialReport(
        reproductions=[
            MethodologyReproduction("Qatalyst", "DCF", 300, 400, 310, 405, 0.9),
            MethodologyReproduction("Evercore", "Comps", 250, 350, 240, 340, 0.8),
            MethodologyReproduction("X", "N/A", None, None, None, None, None),
        ]
    )
    assert rep.mean_overlap == pytest.approx(0.85)
    assert FairnessDifferentialReport(reproductions=[]).mean_overlap is None


# --------------------------------------------------------------------------- #
# interfaces: MergerModelBundle.primary_combination
# --------------------------------------------------------------------------- #
def _empty_statements() -> StatementSet:
    return StatementSet(periods=[FYE_2024], rows={LineItem.REVENUE: [1.0]}, n_hist=0)


def _combo(name: str, disclosed: bool) -> object:
    from src.interfaces import CombinationResult

    return CombinationResult(
        synergy_case=SynergyCase(
            name=name, run_rate_annual=0.0, phase_in=[0.0], is_disclosed=disclosed
        ),
        proforma_statements=_empty_statements(),
        eps_bridge=[],
        contribution=ContributionAnalysis(0, 0, 0, 0, 0, 0, 0.5, 0.5),
    )


def _bundle(combos) -> MergerModelBundle:
    meta_a = CompanyMeta(cik="0000883241", ticker="SNPS", name="Synopsys")
    meta_t = CompanyMeta(cik="0001013462", ticker="ANSS", name="ANSYS")
    terms = DealTerms(
        acquirer_ticker="SNPS",
        target_ticker="ANSS",
        acquirer_name="Synopsys",
        target_name="ANSYS",
        announce_date=date(2024, 1, 16),
        close_date=None,
        consideration_type=ConsiderationType.MIXED,
    )
    deal = DealResult(
        consideration=Consideration(197.0, 105.0, 302.0, 1.0, 197.0, 105.0, 302.0),
        sources_and_uses=SourcesAndUses(sources={"a": 1.0}, uses={"b": 1.0}),
        ppa=PurchasePriceAllocation(1, 1, 0, 1, 0, 0, 0, 1, 0),
    )
    return MergerModelBundle(
        acquirer=meta_a,
        target=meta_t,
        terms=terms,
        acquirer_statements=_empty_statements(),
        target_statements=_empty_statements(),
        acquirer_assumptions=ProjectionAssumptions(),
        target_assumptions=ProjectionAssumptions(),
        deal_assumptions=DealAssumptions(),
        deal=deal,
        combinations=combos,
    )


def test_primary_combination_prefers_disclosed():
    b = _bundle([_combo("Our case", False), _combo("Management", True)])
    assert b.primary_combination().synergy_case.name == "Management"
    b2 = _bundle([_combo("Our case", False)])
    assert b2.primary_combination().synergy_case.name == "Our case"


def test_statement_set_series_missing_is_none():
    ss = _empty_statements()
    assert ss.series(LineItem.REVENUE) == [1.0]
    assert ss.series(LineItem.GOODWILL) == [None]  # honest unknown


def test_combination_accretion_by_year():
    from src.interfaces import CombinationResult

    bridges = [
        EPSBridge(
            year=FYE_2024,
            acquirer_standalone_ni=0,
            target_standalone_ni=0,
            incremental_interest_aftertax=0,
            foregone_interest_aftertax=0,
            incremental_da_aftertax=0,
            synergies_aftertax=0,
            pro_forma_net_income=0,
            acquirer_standalone_shares=0,
            new_shares_issued=0,
            pro_forma_shares=0,
            acquirer_standalone_eps=5.0,
            pro_forma_eps=5.5,
        )
    ]
    cr = CombinationResult(
        synergy_case=SynergyCase("x", 0.0, [0.0]),
        proforma_statements=_empty_statements(),
        eps_bridge=bridges,
        contribution=ContributionAnalysis(0, 0, 0, 0, 0, 0, 0.5, 0.5),
    )
    assert cr.accretion_by_year() == [pytest.approx(0.10)]


def test_sensitivity_containers():
    grid = SensitivityGrid(
        year_idx=0,
        row_label="premium",
        col_label="synergies",
        row_values=[0.2, 0.3],
        col_values=[100.0, 200.0],
        values=[[0.01, 0.02], [-0.01, 0.0]],
    )
    ss = SensitivitySet(premium_x_synergies=grid, consideration_mix=grid, breakeven_synergies=150.0)
    assert ss.breakeven_synergies == 150.0
    assert ss.premium_x_synergies.values[1][0] == -0.01
