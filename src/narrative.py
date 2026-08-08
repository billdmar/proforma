"""Memo narrative — the analyst's prose (ORCH judgment, never delegated).

``SNPS_ANSS_NARRATIVE`` maps each memo section key to its prose. The report
template (``src/report/template.py``) injects these into the M&A committee memo;
numeric claims live in the template's ``<table>`` exhibits (engine-computed,
report-lint-verified), so this prose carries argument, context, and the
labeled disclosed-vs-ours voice — never a hand-typed number presented as fact.

Discipline (docs/MEMO_SPEC.md §Voice):
* Disclosed facts (deal terms, Qatalyst's analyses, management's projections)
  are attributed to the filing. Our modeling choices and synergy cases are
  explicitly labeled "our assumption."
* This is an educational reconstruction; no verdict on whether the deal "should"
  happen; no endorsement implied.
* Every paragraph is written to be delivered aloud in an interview.

Figures referenced in prose (all engine-computed, cross-checked in the tables):
equity purchase price ~$34.1B; consideration $197.00 cash + 0.3450 SNPS share
(~$390.19 implied, 28.7% premium); goodwill ~$22.6B on an $8.0B intangible
step-up (~$0.8B/yr incremental amortization); accretion/(dilution) −38.5%→−20.6%
(base) / −42.1%→−24.0% (conservative) over Yr1–5; breakeven synergies ~$1.25B;
standalone ANSYS DCF ~$140 (Gordon) / ~$264 (exit); fairness mean overlap 67.3%.
"""

from __future__ import annotations

SNPS_ANSS_NARRATIVE: dict[str, str] = {
    # --- 1. Deal overview & timeline -------------------------------------
    "deal_overview": (
        "On January 16, 2024, Synopsys (NASDAQ: SNPS) agreed to acquire ANSYS "
        "(NASDAQ: ANSS) in a cash-and-stock transaction. Per the merger "
        "agreement disclosed in ANSYS's definitive proxy (DEFM14A, SEC accession "
        "0001140361-24-020334), each ANSYS share converts into $197.00 in cash "
        "plus 0.3450 of a Synopsys share. On the December 21, 2023 unaffected "
        "date the mix implied roughly $390.19 per ANSYS share — about a 28.7% "
        "premium to ANSYS's unaffected close and an aggregate equity purchase "
        "price near $34 billion. The transaction closed on July 17, 2025 after "
        "regulatory clearances; ANSYS deregistered (Form 15-12G) shortly after. "
        "This memo reconstructs the economics of that transaction from the public "
        "filings and is an educational exercise, not investment advice."
    ),
    # --- 2. Strategic rationale ------------------------------------------
    "strategic_rationale": (
        "As disclosed in the proxy and joint communications, the strategic logic "
        "is a 'silicon-to-systems' design stack: Synopsys's electronic design "
        "automation (chip design) combined with ANSYS's multiphysics simulation "
        "(how those chips and the systems around them behave thermally, "
        "mechanically, electromagnetically). Our commentary (our view, not a "
        "disclosed fact): the two product lines are complementary rather than "
        "overlapping, which is why the deal reads as a capability acquisition — "
        "buying a simulation franchise that would be slow and risky to build — "
        "far more than a cost-synergy story. That framing matters for the "
        "accretion analysis below: the price is underwritten by strategic value "
        "and revenue opportunity, not by near-term earnings arithmetic."
    ),
    # --- 3. Target valuation ---------------------------------------------
    "target_valuation": (
        "We value ANSYS on a standalone basis three ways and frame each against "
        "the ~$390.19 offered consideration. Our own discounted-cash-flow model "
        "(our assumptions: ~9.4% WACC — ANSYS is roughly net cash, so the rate is "
        "essentially its cost of equity — 3.0% terminal growth, and a 22x exit "
        "EBITDA cross-check) implies a standalone value well below the offer. "
        "That gap is the point, not a flaw: it quantifies how much of the price "
        "is premium for control, synergies, and strategic fit rather than "
        "ANSYS's standalone cash flows. Trading and precedent multiples — here "
        "we reuse the multiple ranges Qatalyst itself disclosed, applied to "
        "ANSYS's metrics — bracket a higher range that overlaps the offer, "
        "consistent with software assets changing hands at premium multiples. "
        "The triangulation exhibit shows all three against the offer."
    ),
    # --- 4. Structure & financing ----------------------------------------
    "structure_financing": (
        "The cash leg (~$17B of the ~$34B) was funded, per Synopsys's disclosures "
        "(SEC accession 0001140361-25-026140), with $10.0 billion of senior notes "
        "issued in March 2025 and a $4.3 billion term loan drawn at closing, plus "
        "cash on hand; a bridge facility was arranged and then terminated once "
        "the permanent financing was in place. Our model uses ~$14.3B of new debt "
        "and roughly $3.0B of balance-sheet cash so that sources equal uses "
        "exactly. The blended cost of the new debt (~5.0%) is our assumption — "
        "the individual tranche coupons are not in the cached filings — chosen as "
        "a defensible investment-grade-technology cost across the notes and the "
        "SOFR-based term loan. The sources & uses exhibit ties to the cent."
    ),
    # --- 5. Purchase price accounting ------------------------------------
    "purchase_price_accounting": (
        "Purchase accounting rewrites the target's balance sheet at fair value. "
        "We write off ANSYS's existing goodwill, step up identifiable intangibles "
        "by $8.0 billion (our assumption; 10-year life) — deliberately "
        "conservative versus the ~$12.5 billion Synopsys actually recorded — and "
        "book the deferred-tax liability that the step-up creates at the 21% "
        "statutory rate. Goodwill is the plug that makes the entry balance: "
        "equity purchase price less the fair value of net identifiable assets, "
        "landing near $22.6 billion (versus ~$26.9 billion actually reported — a "
        "smaller step-up leaves more in goodwill; the two move together). The "
        "consequence that drives the next section: the $8.0B step-up amortizes at "
        "roughly $0.8 billion per year, a real, non-cash charge to pro forma GAAP "
        "earnings."
    ),
    # --- 6. Accretion / dilution -----------------------------------------
    "accretion_dilution": (
        "On a GAAP basis the deal is dilutive to Synopsys EPS throughout the "
        "horizon — roughly −38% in Year 1 improving to about −21% by Year 5 in "
        "our base synergy case (worse in the conservative case). Three forces "
        "drive it: ~$0.8B/yr of step-up amortization, after-tax interest on the "
        "new debt, and the ~30.1 million new Synopsys shares issued. Why Year-1 "
        "dilution is not automatically a 'bad deal': first, the single largest "
        "driver — step-up amortization — is a non-cash accounting charge, so on a "
        "cash-EPS (ex-amortization) basis the picture is materially less dilutive "
        "and is exactly how management and the Street judge software deals; "
        "second, dilution narrows every year as the target grows and synergies "
        "phase in; and third, a capability acquisition is underwritten by "
        "multi-year revenue and strategic value, not Year-1 EPS. The EPS-bridge "
        "and sensitivity exhibits decompose the walk and show how it moves with "
        "premium and synergies."
    ),
    # --- 7. Synergies ----------------------------------------------------
    "synergies": (
        "The proxy discusses synergies only qualitatively and discloses no "
        "quantified run-rate, so — unlike some deals — there is no management "
        "figure to quote. Both cases here are therefore explicitly our "
        "assumptions, sized against ANSYS's ~$1.5B operating-cost base: a "
        "conservative $150M annual run-rate and a base $300M run-rate, each "
        "phased in over three years. The useful framing is breakeven: Year-1 EPS "
        "accretion would require on the order of $1.25 billion of annual "
        "synergies — far above either case and well beyond what cost synergies "
        "alone plausibly deliver. Read correctly, that says the deal does not pay "
        "for itself on near-term cost savings; it is a revenue-and-strategy bet, "
        "which is consistent with how the parties described it."
    ),
    # --- 8. Risks --------------------------------------------------------
    "risks": (
        "Regulatory: a large software-tooling combination drew antitrust review "
        "in multiple jurisdictions; the deal ultimately closed with remedies, but "
        "cross-border merger review is a genuine timeline and deal-certainty "
        "risk.|Integration: capability acquisitions live or die on integration — "
        "combining go-to-market motions and product roadmaps across EDA and "
        "simulation without disrupting either franchise.|Financing: ~$14.3B of "
        "new debt raises leverage and interest expense; a higher-for-longer rate "
        "path makes the debt-funded portion more dilutive (quantified in the "
        "sensitivity grid).|Market & execution: the standalone valuation gap "
        "means the premium is underwritten by synergies and growth that must "
        "actually materialize; if they don't, the economic return compresses even "
        "though the strategic logic holds.|These are our risk read, not a "
        "prediction, and the memo passes no verdict on whether the deal should "
        "have occurred."
    ),
    # --- 9. Fairness-opinion comparison ----------------------------------
    "fairness_comparison": (
        "The strongest validation of the mechanics is external: we take the "
        "assumptions ANSYS's financial advisor, Qatalyst Partners, disclosed in "
        "the proxy — their discount-rate band, their multiple ranges, their "
        "management-case cash-flow stream — and run them through our own engine "
        "to see whether we reproduce the implied per-share ranges they published. "
        "We do, with a mean overlap of about 67%: the multiple-based methods "
        "overlap roughly 77–79%, and the DCF overlaps about 46%. The DCF gap is "
        "explained, not tuned away: the proxy tabulates only the first of three "
        "management cases, so our single-case DCF range is narrower and sits in "
        "the upper part of Qatalyst's union-of-three-cases band. Reproducing a "
        "banker's disclosed valuation from their own inputs — and explaining "
        "where and why it differs — is what a fairness opinion can and cannot "
        "tell you, made concrete."
    ),
}
