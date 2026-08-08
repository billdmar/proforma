"""Deal #2 memo narrative — the analyst's prose (Cisco/Splunk).

``CSCO_SPLK_NARRATIVE`` maps each memo section key to its prose, mirroring
``src.narrative.SNPS_ANSS_NARRATIVE`` (same nine section keys, same voice
discipline). The report template injects these into the M&A committee memo;
numeric claims live in the template's ``<table>`` exhibits (engine-computed,
report-lint-verified), so this prose carries argument, context, and the
labeled disclosed-vs-ours voice — never a hand-typed number presented as fact.

Discipline (docs/MEMO_SPEC.md §Voice):
* Disclosed facts (deal terms, Qatalyst's and Morgan Stanley's analyses,
  management's projections) are attributed to the filing. Our modeling choices
  and synergy cases are explicitly labeled "our assumption."
* This is an educational reconstruction; no verdict on whether the deal "should"
  happen; no endorsement implied; no advisor/party disparaged.
* Every paragraph is written to be delivered aloud in an interview.

This deal is the deliberate mirror image of deal #1 (Synopsys/ANSYS): an
all-cash, debt-financed acquisition of a loss-making, negative-book-equity
high-growth software target. The honest result is heavy early dilution — owned
plainly as a strategic/growth bet, not an EPS deal.

Figures referenced in prose (all engine-computed, cross-checked in the tables):
equity purchase price ~$26.5B; $157.00/share all cash, ~31.3% premium, zero new
Cisco shares; goodwill ~$20.9B on a $9.0B intangible step-up (~$0.9B/yr
incremental amortization); accretion/(dilution) −12.3%→−3.3% (base) /
−13.2%→−4.3% (conservative) over Yr1–5; breakeven synergies ~$2.1B; standalone
Splunk DCF ~$68 (Gordon) / ~$154 (exit); two-advisor fairness — reproducible
methods overlap: Qatalyst DCF ~25% + Selected Companies ~63%, Morgan Stanley
DCF ~26% (mean ~38% across the reproducible set).
"""

from __future__ import annotations

CSCO_SPLK_NARRATIVE: dict[str, str] = {
    # --- 1. Deal overview & timeline -------------------------------------
    "deal_overview": (
        "On September 21, 2023, Cisco Systems (NASDAQ: CSCO) agreed to acquire "
        "Splunk (NASDAQ: SPLK) in an all-cash transaction. Per the merger "
        "agreement disclosed in Splunk's definitive proxy (DEFM14A, SEC accession "
        "0001140361-23-050211), each Splunk share converts into $157.00 in cash — "
        "no stock component. On the September 20, 2023 unaffected date that price "
        "represented roughly a 31% premium to Splunk's $119.59 close, an aggregate "
        "equity purchase price near $26.5 billion. The transaction closed on "
        "March 18, 2024 after regulatory clearances. This memo reconstructs the "
        "economics of that transaction from the public filings and is an "
        "educational exercise, not investment advice."
    ),
    # --- 2. Strategic rationale ------------------------------------------
    "strategic_rationale": (
        "As disclosed in the proxy and joint communications, the strategic logic "
        "is to combine Cisco's networking and security franchise with Splunk's "
        "security-analytics and observability platform — extending Cisco into "
        "AI-era security and full-stack observability across a large installed "
        "base. Our commentary (our view, not a disclosed fact): this is a growth "
        "and capability acquisition, not a cost-synergy story. Cisco is paying a "
        "premium for a fast-growing, still-unprofitable software asset to buy a "
        "position it would be slow to build organically. That framing matters for "
        "the accretion analysis below: the price is underwritten by revenue "
        "opportunity and strategic fit, and — unusually — by an explicit bet that "
        "Splunk's margins inflect toward mature-software profitability over time. "
        "It is emphatically not underwritten by near-term earnings arithmetic."
    ),
    # --- 3. Target valuation ---------------------------------------------
    "target_valuation": (
        "We value Splunk on a standalone basis and frame it against the $157.00 "
        "offered price. Our own discounted-cash-flow model (our assumptions: "
        "~10.3% WACC — a higher-beta growth-software rate than a mature name would "
        "carry, and Splunk holds essentially no debt so the rate is close to its "
        "cost of equity — 3.0% terminal growth, with a 22x exit-EBITDA "
        "cross-check) is deliberately a stress case: Splunk is only barely "
        "profitable at our base year, so the Gordon-growth version implies a value "
        "well below the offer while the exit-multiple version lands much closer. "
        "We report that spread honestly rather than tuning it away — a low-margin, "
        "high-growth target is exactly where a single-point DCF is least "
        "informative and a multiple cross-check earns its keep. The gap to the "
        "offer is the point: it quantifies how much of the price is premium for "
        "control, future margin expansion, and strategic fit rather than Splunk's "
        "current standalone cash flows."
    ),
    # --- 4. Structure & financing ----------------------------------------
    "structure_financing": (
        "This is an all-cash deal, so there is no stock leg and Cisco issues no "
        "new shares — the entire ~$26.5B equity purchase price plus fees is funded "
        "with debt and balance-sheet cash. Per Cisco's disclosures, the company "
        "raised $22.0 billion of new senior notes in February 2024 across multiple "
        "tranches (a bridge facility was arranged and then terminated once the "
        "permanent financing was in place). Our model uses that $22.0B of new debt "
        "and funds the remainder — roughly $4.6B — from cash on hand so that "
        "sources equal uses exactly, with no residual plug. The blended cost of "
        "the new debt (~5.0%) is our assumption — the individual tranche coupons "
        "are not needed for the blended interest line — chosen as a defensible "
        "2024 investment-grade-technology cost across the maturities. The sources "
        "& uses exhibit ties to the cent."
    ),
    # --- 5. Purchase price accounting ------------------------------------
    "purchase_price_accounting": (
        "Purchase accounting rewrites the target's balance sheet at fair value, "
        "and Splunk is an instructive case: its reported book equity is negative "
        "(about −$110 million), and it carries ~$1.4 billion of existing goodwill "
        "that we write off before re-allocation. We step up identifiable "
        "intangibles by $9.0 billion (our assumption; 10-year life) — Splunk's "
        "~$3.7B revenue base carries substantial developed-technology and "
        "customer-relationship intangibles — and book the deferred-tax liability "
        "the step-up creates at the 21% statutory rate. Goodwill is the plug that "
        "makes the entry balance: equity purchase price less the fair value of net "
        "identifiable assets. Because those identifiable net assets are negative, "
        "almost the entire price becomes intangibles plus goodwill, with goodwill "
        "landing near $20.9 billion — exactly what you expect when a high-growth "
        "software target with a thin balance sheet is bought at a premium. The "
        "consequence that drives the next section: the $9.0B step-up amortizes at "
        "roughly $0.9 billion per year, a real, non-cash charge to pro forma GAAP "
        "earnings."
    ),
    # --- 6. Accretion / dilution -----------------------------------------
    "accretion_dilution": (
        "On a GAAP basis the deal is dilutive to Cisco EPS throughout the horizon "
        "— roughly −12% in Year 1 improving to about −3% by Year 5 in our base "
        "synergy case (worse in the conservative case) — and we own that plainly. "
        "Three forces drive it, and because this is an all-cash deal, none of them "
        "is offset by a lower share count: ~$0.9B/yr of step-up amortization, "
        "after-tax interest on the full $22B of new debt, and the drag of a "
        "target that is only modestly profitable early in our ramp. Why Year-1 "
        "dilution is not automatically a 'bad deal': first, the step-up "
        "amortization is a non-cash accounting charge, so on a cash-EPS "
        "(ex-amortization) basis the picture is less dilutive and is exactly how "
        "management and the Street judge software deals; second, dilution narrows "
        "every year as Splunk's revenue compounds and its margin inflects and as "
        "synergies phase in; and third, a growth-and-capability acquisition is "
        "underwritten by multi-year revenue and strategic value, not Year-1 EPS. "
        "The EPS-bridge and sensitivity exhibits decompose the walk and show how it "
        "moves with premium and synergies. This is the mirror image of a "
        "stock-financed deal for a profitable target — a useful contrast to keep in "
        "an interview."
    ),
    # --- 7. Synergies ----------------------------------------------------
    "synergies": (
        "The proxy discusses the strategic rationale only qualitatively and "
        "discloses no quantified run-rate, so — unlike some deals — there is no "
        "management synergy figure to quote. Both cases here are therefore "
        "explicitly our assumptions, sized against Splunk's ~$3.9B FY2023 "
        "operating-cost base: a conservative $200M annual run-rate and a base "
        "$400M run-rate, each phased in over three years. The useful framing is "
        "breakeven: zeroing Year-1 EPS dilution would require on the order of "
        "$2.1 billion of annual synergies — several times either case and far "
        "beyond what cost synergies alone plausibly deliver for a target this "
        "size. Read correctly, that says the deal does not pay for itself on "
        "near-term cost savings; it is a revenue-and-strategy bet on security and "
        "observability, which is consistent with how the parties described it."
    ),
    # --- 8. Risks --------------------------------------------------------
    "risks": (
        "Margin execution: our thesis depends on Splunk's operating margin "
        "inflecting from roughly breakeven toward mature-software levels over the "
        "projection; if that ramp stalls, the dilution persists longer and the "
        "standalone value falls short of the price.|Integration: capability "
        "acquisitions live or die on integration — combining go-to-market motions "
        "and product roadmaps across networking, security, and observability "
        "without disrupting either franchise or Splunk's growth.|Financing & "
        "rates: the full $22B of new debt raises leverage and interest expense; a "
        "higher-for-longer rate path makes an all-cash, debt-funded deal more "
        "dilutive (quantified in the sensitivity grid), with no share-count offset "
        "because no equity was issued.|Regulatory: a large software combination "
        "drew antitrust review across jurisdictions; the deal ultimately closed, "
        "but cross-border merger review is a genuine timeline and deal-certainty "
        "risk.|These are our risk read, not a prediction, and the memo passes no "
        "verdict on whether the deal should have occurred."
    ),
    # --- 9. Fairness-opinion comparison ----------------------------------
    "fairness_comparison": (
        "Splunk's board received fairness opinions from TWO financial advisors — "
        "Qatalyst Partners and Morgan Stanley — and we reproduce both. For each, "
        "we take the assumptions the advisor disclosed in the proxy (their "
        "discount-rate and perpetuity-growth bands for the DCF, their multiple "
        "ranges for the market analyses, and the management-case cash-flow stream) "
        "and run them through our own engine to see whether we reproduce the "
        "implied per-share ranges they published. Where the proxy discloses a "
        "reproducible assumption set, we reproduce the range: our Gordon-growth "
        "DCF overlaps Qatalyst's disclosed DCF range by about 25% and Morgan "
        "Stanley's by about 26% (both advisors' disclosed ranges are the union "
        "across several projection scenarios, so our single-stream reproduction is "
        "narrower and sits inside the upper part of each band), and our "
        "revenue-multiple reproduction overlaps Qatalyst's Selected-Companies "
        "range by about 63%. For the remaining market sub-analyses — the "
        "Selected/Precedent Transactions and Public Trading Comparables tables — "
        "the proxy publishes an implied range but not a single reproducible "
        "assumption set (each is itself a union across several NTM revenue, EBITDA, "
        "and LFCF multiple tables), so we report an honest 'not reproduced' rather "
        "than manufacture a fit. Reproducing two independent bankers' disclosed "
        "valuations from their own inputs — and being explicit about where the "
        "disclosure does and does not let us — is what a fairness opinion can and "
        "cannot tell you, made concrete."
    ),
}
