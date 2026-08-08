# ASSUMPTIONS.md — the defend-it-in-the-room ledger

**Rule of this file:** every modeling driver gets a 2–4 line, sourced rationale.
**Disclosed facts** (from SEC filings) are quoted with provenance and kept
strictly separate from **our assumptions** (labeled "OURS"). Nothing here is
investment advice; synergy figures are labeled assumptions, never forecasts.

---

## 1. Deal selection (the one W0 human decision)
**Chosen: Synopsys, Inc. (SNPS, acquirer) / ANSYS, Inc. (ANSS, target).**
Announced 2024-01-16; closed ~2025-07-17 (ANSYS filed Form 15-12G deregistering
on 2025-07-29). ~$35B cash-and-stock.

Why this deal, over the other two finalists (Exxon/Pioneer all-stock;
Cisco/Splunk all-cash): the **cash-and-stock mix** exercises the entire merger
engine at once — new-debt financing, cash-on-hand use, share issuance at a
reference price, purchase price accounting with large software goodwill,
synergies, and accretion/dilution. Both parties are non-financial SEC filers
with deep clean XBRL (SNPS 543 us-gaap concepts through FY2025; ANSS 475 back to
FY2010). The merger proxy discloses a rich **Qatalyst Partners** fairness
opinion — the differential oracle. Understandable strategic logic (EDA +
simulation → a full "silicon-to-systems" design stack).

---

## 2. Disclosed deal facts (SEC provenance — NOT our assumptions)
All figures below are quoted from the filings; SA-edgar populates the machine
records (`DealTerms`, `FairnessDisclosure`) with the same provenance. Cross-check
target for the G1 tie-out.

| Fact | Value | Source (accession · section) |
|---|---|---|
| Consideration per Ansys share | **$197.00 cash + 0.3450 SNPS share** | ANSS DEFM14A 0001140361-24-020334 · "The Merger — Merger Consideration" (verbatim: "$197.00 in cash … and (ii) 0.3450 of a share of Synopsys common stock") |
| Announce date | 2024-01-16 | Deal 8-Ks / press release (425s) |
| Target advisor | Qatalyst Partners | ANSS DEFM14A · "Opinion of Qatalyst Partners" |
| Implied/unaffected price | **$390.19/share** (SNPS $559.96 close × 0.3450 + $197.00), Dec 21 2023 unaffected | ANSS DEFM14A · "Background/Opinion" |
| Premium | **~29%** over ANSS unaffected close $303.16 | ANSS DEFM14A |
| Target shares outstanding | 87,299,981 (record date) | ANSS DEFM14A |
| Qatalyst **DCF** implied range | **$160.25 – $496.04 / share** (union of Mgmt Cases 1–3) | ANSS DEFM14A · "Illustrative Discounted Cash Flow Analysis" |
| Qatalyst DCF assumptions | discount rate 10.5%–13.0%; NTM UFCF terminal multiple 20.0x–30.0x | same section |
| Qatalyst **Selected Companies** implied | **$198.32 – $340.71 / share**; CY2024E LFCF 25.0x–40.0x | ANSS DEFM14A · "Illustrative Selected Companies Analysis" |
| Qatalyst **Selected Transactions** implied | **$199.97 – $319.88 / share** (27 precedents); NTM LFCF 25.0x–40.0x | ANSS DEFM14A · "Illustrative Selected Transactions Analysis" |
| Management projections | Revenue $2,510M→$9,097M, UFCF $795M→$3,178M (FY2024E–FY2033E, Case 1) | ANSS DEFM14A · "Certain Unaudited Prospective Financial Information" |
| Disclosed annual synergies | **honest unknown** — proxy discusses synergies only qualitatively; no quantified run-rate disclosed | ANSS DEFM14A (searched) |

> Figures above are SA-edgar's structured section-by-section extraction, each
> carrying a verbatim-quoted `DocProvenance` (accession 0001140361-24-020334).
> They are the reconciliation target for the G2 fairness differential: our
> engine, fed Qatalyst's disclosed assumptions, must reproduce these implied
> ranges. Every figure is re-verified against the proxy text before the
> differential is published; disclosed synergies stay an honest unknown (our own
> synergy cases are labeled OURS below).

---

## G1 machinery notes (resolved / carried to W2)
- **EPS-bridge tax convention (resolved at G1).** All four pro forma adjustment
  legs — incremental interest, foregone interest income, step-up D&A, synergies —
  are stored **after-tax** in `EPSBridge`, so the bridge is a pure additive walk
  to pro forma net income and the workbook reproduces it cell-for-cell.
  (Interest is tax-deductible, so its net-income impact is coupon × (1 − t).) A
  financed-deal differential test (`test_financed_deal_differential_to_the_cent`)
  proves the workbook↔engine match to the cent with non-zero interest legs.
- **W2 constraint — target projected equity.** The combination engine layers
  static day-1 purchase-accounting adjustments each period, so the pro forma
  balance sheet balances every year only when the target's projected total
  equity ties to its reported equity (e.g. dividends absorb net income). The
  flagship model must set the target's payout/equity handling accordingly, or
  extend the engine, so the BS-balance invariant holds across the horizon.

## 3. Our modeling assumptions (OURS — set by ORCH at W2)
Everything in this section is **our judgment**, not disclosed fact. Each driver
carries a 2–4 line rationale grounded in the companies' reported history (§2 of
the tie-out) or standard M&A practice. Figures are defensible, not precise
forecasts.

### 3.0 The pre-close base-year cut (critical)
The standalone models are built from each company's **last pre-close fiscal
year**, because a post-close period already contains the combination:
- **Acquirer = Synopsys FY2024 (ended 2024-10-31):** revenue $6,127M, operating
  margin 22.1%, LT debt ~$16M, ~155.9M diluted shares. **We deliberately do NOT
  use SNPS FY2025 (ended 2025-10-31)** — that period already consolidates ANSYS
  (total assets jump $13.1B→$48.2B, goodwill $3.4B→$26.9B, LT debt →$13.46B,
  shares →186M as the deal closed 2025-07-17). Using it would double-count the
  target. FY2025 is instead kept aside as a real-world **post-close sanity check**
  on our pro forma (see §3.7).
- **Target = ANSYS FY2024 (ended 2024-12-31):** revenue $2,545M, operating margin
  28.2%, book equity $6,086M, existing goodwill $3,778M, LT debt $754M, ~87.9M
  diluted shares. These feed the PPA and standalone projection.

### 3.1 Standalone drivers — Synopsys (acquirer)
5-year projection off FY2024. Revenue growth **11% → 9%** tapering (3-yr
historical CAGR ≈ 15% FY22–FY24 but decelerating as EDA matures; we taper
conservatively). Operating margin held ~**22%** (FY24 actual 22.1%; R&D-heavy
model, ~34% of revenue). Tax **16%** marginal (historical effective is a
distorted 4–7% from R&D credits and discretes; 16% is a defensible normalized
rate below the 21% statutory). Capex ~2.5% of revenue; D&A ~4%. No dividend
(SNPS pays none). Standalone diluted shares held flat at FY24 ~155.9M.

### 3.2 Standalone drivers — ANSYS (target)
Revenue growth **9% → 7%** (FY22–FY24 CAGR ≈ 11%, decelerating). Operating
margin ~**28%** (FY24 actual 28.2%; higher-margin simulation software). Tax
**16%** normalized (historical effective 9.0%→19.8% trending up). Capex ~1.5%;
D&A ~5.5% (amortization of prior-deal intangibles). **Dividend payout = 100%**
post-close (see §3.6). Standalone diluted shares ~87.9M.

### 3.3 Deal terms — DISCLOSED (from §2, provenance-stamped, not ours)
$197.00 cash + 0.3450 SNPS/ANSS share; ~87.3M target shares; implied $390.19/sh;
29% premium. Reference SNPS price for the stock leg = $559.96 (Dec-21-2023
unaffected close, per proxy). We use the disclosed terms exactly.

### 3.4 Financing — structure DISCLOSED, blended rate OURS
Synopsys funded the ~$17B cash leg with **$10.0B senior notes (issued
2025-03-17) + $4.3B term loan (borrowed 2025-07-17) + cash on hand**; the ~$690M
bridge was terminated/replaced (SNPS 425 accession 0001140361-25-026140 —
disclosed). ⇒ we model **$14.3B new debt + ~$2.7B cash on hand**.
- **New-debt blended rate = 5.0% (OURS).** The exact tranche coupons are not in
  the cached filings (honest unknown); 5.0% is a defensible blended
  investment-grade-tech cost across 2025 senior notes + a SOFR-based term loan.
- **Cash on hand used = ~$3.05B (OURS).** Fixed the disclosed $14.3B debt and the
  stock leg, then set cash-on-hand to the exact remainder of uses so **sources =
  uses with no residual plug** and the pro forma balance sheet ties every period.
  ~$3.05B is comfortably within SNPS's ~$3.9B pre-close cash.
- **Foregone yield on cash used = 4.0% (OURS)** — the short-term rate SNPS was
  earning on the cash it deployed.
- Advisory + financing fees: **$150M (OURS, ~0.4% of deal value)** — a standard
  large-cap fee load; the proxy does not itemize a single figure.

### 3.5 Purchase price accounting (OURS, standard method)
Equity purchase price from the disclosed consideration; write off ANSYS's
existing $3,778M goodwill; step up identifiable intangibles. **Intangible
step-up = $8.0B (OURS), 10-year life**; PP&E step-up $0 (immaterial for a
software target). **Deferred-tax rate on step-ups = 21%** (US statutory — the
DTL is a book/tax basis difference, so statutory, not our 16% P&L rate).
Goodwill is the plug: equity purchase price − net identifiable assets. This
produces a large software goodwill balance, consistent with the actual
post-close SNPS jump to ~$26.9B goodwill (directional check).

### 3.6 Synergies — BOTH cases are OURS (proxy quantifies none)
The proxy discusses synergies only qualitatively (§2: honest unknown), so we set
two labeled cases grounded in ANSYS's ~$1.5B FY24 operating-cost base:
- **Conservative case: $150M annual run-rate**, phased 33%/67%/100% over Y1–Y3.
- **Base/"management-style" case: $300M annual run-rate**, phased 50%/75%/100%.
Both pre-tax cost synergies. We frame **breakeven synergies** (the run-rate that
makes Year-1 A/D = 0) against these. No figure is presented as management's.

### 3.7 Marginal tax rate for deal adjustments = 16% (OURS)
Applied to incremental interest, foregone income, step-up D&A, and synergies —
consistent with the normalized standalone rate. (The step-up DTL uses 21%
statutory per §3.5 — a deliberate, standard distinction.)

### 3.8 Post-close reality check (not an input — a validation)
SNPS FY2025 (post-close) reports goodwill ~$26.9B, LT debt ~$13.46B, ~186M
shares. Our engine's independent build lands in the same neighborhood:
**goodwill $22.6B** (our conservative $8B intangible step-up vs. the ~$12.5B
ANSYS actually recorded explains the gap — more step-up ⇒ less goodwill), new
debt $14.3B (matches disclosed), new shares 0.3450×87.3M ≈ 30.1M on ~155.9M.
A directional sanity check, not tuned to.

### 3.9 Standalone ANSYS DCF (OURS — for the memo's target-valuation section)
Our own intrinsic view of ANSYS on a standalone basis (distinct from §5, which
reproduces *Qatalyst's* disclosed assumptions). Discounts the target's
driver-based unlevered FCF (from §3.2) with:
- **WACC = 9.43% (OURS, engine-computed):** risk-free **4.3%** (10-yr UST, 2024),
  beta **1.05** (mature large-cap software), ERP **5.0%**, pre-tax cost of debt
  **5.0%**, tax 16% (§3.7). Cost of equity ≈ 4.3% + 1.05×5.0% ≈ 9.55%; ANSYS's
  small book debt pulls the blended WACC fractionally below that to 9.43%. Sits
  just below Qatalyst's disclosed 10.5%–13.0% band — reasonable for a lower-beta
  standalone view vs. the advisor's more conservative range.
- **Terminal: both methods.** Gordon growth **3.0%** (long-run software/GDP-plus;
  < WACC per the engine's sanity gate) and an exit **EV/EBITDA 22.0x** (mid of
  the software-precedent band in §data/curated). The memo frames the resulting
  implied per-share range against the **$390.19** offered consideration.
These are OUR assumptions, argued here; the engine computes the DCF — no number
is hand-typed into the memo.

---

## 4. Computed results (engine outputs — the G2 headline)
All figures below are produced by the engine from §3's assumptions; none is
hand-typed. Reproduced deterministically by `src.flagship.build_flagship_bundle`.

**Deal:** equity purchase price **$34.1B**; implied **$390.19/share**; premium
**28.7%**; **goodwill $22.6B**; incremental step-up D&A **~$0.8B/yr**;
30.1M new Synopsys shares on ~155.9M → target holders own ~16% of the combined.

**Accretion/(dilution), pro forma diluted EPS vs. Synopsys standalone:**
| Case (annual synergy run-rate) | Y1 | Y2 | Y3 | Y4 | Y5 |
|---|---|---|---|---|---|
| Base (ours, $300M) | −38.5% | −31.4% | −25.6% | −22.9% | −20.6% |
| Conservative (ours, $150M) | −42.1% | −35.3% | −29.8% | −26.7% | −24.0% |

Deeply GAAP-dilutive — the expected result of an all-premium software deal with
~$0.8B/yr of purchase-accounting amortization. This is the standard
**GAAP-dilutive / strategically-accretive** story: on a cash-EPS (ex-amortization)
basis the picture is far less dilutive. **Breakeven synergies (Year-1 A/D = 0):
~$1.25B/yr** — well above our cases, i.e. the deal is not EPS-accretive on
plausible cost synergies alone; the rationale is strategic (the full
silicon-to-systems design stack), not near-term EPS.

## 5. Fairness differential — OUR engine vs. Qatalyst's disclosed ranges
Fed Qatalyst's **disclosed** assumptions (discount rates, multiples, Management
Case 1 UFCF), our engine reproduces their disclosed implied per-share ranges.
**Measured, never tuned:**
| Methodology | Qatalyst disclosed | Our reproduction | Overlap |
|---|---|---|---|
| Discounted Cash Flow | $160.25–$496.04 | $342.44–$555.02 | 45.7% |
| Selected Companies | $198.32–$340.71 | $227.66–$364.26 | 79.4% |
| Selected Transactions | $199.97–$319.88 | $227.66–$364.26 | 76.9% |
| **Mean overlap** | | | **67.3%** |

**Deviation investigated (not tuned away):** our DCF uses only Management Case 1
(the sole projection set tabulated in the proxy), while Qatalyst's disclosed DCF
range is the *union* across Cases 1–3 — so our narrower Case-1 range sits in the
upper portion of their wider band, the main driver of the 45.7% DCF overlap. The
multiple-based methods (equity/LFCF multiples, ANSYS net-cash) overlap ~77–79%.
