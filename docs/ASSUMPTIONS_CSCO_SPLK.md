# ASSUMPTIONS_CSCO_SPLK.md — deal #2 ledger (Cisco / Splunk)

**The P6 generality proof.** This second deal runs through the *same engine* as
Synopsys/ANSYS — no engine code is deal-specific. Only the inputs below (and the
extraction + assembler + narrative modules) are new. Same rule as deal #1:
**disclosed facts** (SEC filings, provenance-stamped) are kept strictly separate
from **our assumptions** ("OURS"); nothing is investment advice.

Why this deal: an **all-cash, debt-financed** acquisition of an **unprofitable,
negative-book-equity** high-growth software target — a deliberately different
shape from deal #1 (cash-and-stock, profitable target). It stress-tests the same
engine on (a) a pure cash/debt structure, (b) a loss-making target, and (c)
negative target equity in the PPA. Two fairness advisors (Qatalyst + Morgan
Stanley) instead of one.

---

## 1. Disclosed deal facts (SEC provenance — NOT our assumptions)
From Splunk's DEFM14A (accession 0001140361-23-050211, filed 2023-10-30) and the
completion 8-K, all extracted by `src/edgar/extract_csco_splk.py`:

| Fact | Value | Source |
|---|---|---|
| Consideration | **$157.00 / share, all cash** | DEFM14A · "Merger Consideration" |
| Premium | **~31%** over $119.59 unaffected close (Sept 20 2023) | DEFM14A · "Reasons for the Merger" |
| Target shares outstanding | 168,536,732 | DEFM14A · "Record Date and Quorum" |
| Announce / close | 2023-09-21 / 2024-03-18 | 425 / Splunk completion 8-K |
| Advisors (to Splunk) | Qatalyst Partners **and** Morgan Stanley | DEFM14A · "Opinion of…" |
| Qatalyst DCF | implied **$100.95–$196.81**; discount 12.0–14.0%, perpetuity 3.0–5.0% | DEFM14A |
| Morgan Stanley DCF | implied **$100.00–$212.00**; discount 11.6–13.5%, growth 3.0–5.0% | DEFM14A |
| Management projections | Revenue $4,038M→$13,462M, UFCF $937M→$5,483M (FY24E–FY34E) | DEFM14A |

Aggregate equity value ≈ $157 × 168.5M ≈ **$26.5B** (~$28B enterprise incl. net
debt/cash-settled equity awards, as widely reported).

## 2. Pre-close base-year cut (critical — same discipline as deal #1)
A post-close period already consolidates the target, so both standalone models
use the **last pre-close fiscal year**:
- **Acquirer = Cisco FY2023 (ended 2023-07-29):** revenue $56.998B (FY23 actual;
  our engine reads the reported line), operating margin ~26%, ~4.07B diluted
  shares, ~$46B equity. **NOT** FY2024/FY2025 — those already include Splunk
  (goodwill jumps to ~$58.7B). Cisco FY2023 goodwill was ~$38–39B (pre-Splunk).
- **Target = Splunk FY2023 (ended 2023-01-31):** revenue $3,653.7M, operating
  margin −6.4% (net loss −$277.9M), **negative book equity −$110.5M**, goodwill
  $1,416.9M, ~162.4M diluted shares.

## 3. Our modeling assumptions (OURS)
### 3.1 Cisco (acquirer) standalone drivers
Mature networking/software leader. Revenue growth **4% → 3%** (low-single-digit,
GDP-plus; Cisco is ex-growth). Operating margin held ~**26%** (FY23 level). Tax
**16%** normalized. Capex ~1.5% of revenue; D&A ~3%. Dividend payout **~50%**
(Cisco pays a large dividend — but for the pro forma BS we model the *combined*
entity; acquirer standalone payout is set so its own equity roll is realistic).
Diluted shares held ~4.07B (no standalone buyback modeled).

### 3.2 Splunk (target) standalone drivers — the judgment call
Splunk was unprofitable at close but rapidly approaching breakeven (operating
margin improved −42.9% → −6.4% in one year; it was a classic "Rule of 40"
software story mid-inflection). We model a **credible margin ramp to
profitability**, consistent with management's disclosed projections (UFCF
$937M in FY24E rising to $5,483M by FY34E — i.e. the Street/advisors already
underwrote a profitable Splunk):
- Revenue growth **15% → 10%** tapering (FY23 grew ~37%; decelerating as it scales).
- Operating margin ramps **2% → 18%** over five years (from ~breakeven toward a
  mature-software margin; more conservative than the ~40% UFCF/revenue the
  management case implies at maturity).
- Tax **16%** once profitable; capex ~2%; D&A ~6% (heavy acquired-intangible
  amortization). **Dividend payout = 100%** post-close (same BS-balancing
  simplification as deal #1 §3.2 — holds target book equity flat).
- **Negative base equity (−$110.5M)** is carried as-is into the PPA — it is the
  reported figure. A target worth ~$26.5B with negative book equity simply means
  almost the entire purchase price becomes step-ups + goodwill (see §3.4).

### 3.3 Financing (structure disclosed; blended rate OURS)
Cisco funded the ~$28B all-cash deal with **$22.0B of new senior notes** (issued
Feb 2024 across multiple tranches — disclosed) plus **cash on hand**; a bridge
facility was arranged and terminated. We model **$22.0B new debt** at a blended
**5.0% (OURS** — 2024 IG coupons across 2–30yr tranches; exact per-tranche
coupons not needed for the blended interest line) plus the remainder from cash
on hand at a **4.0% foregone yield (OURS)**. Advisory + financing fees **$150M
(OURS)**.

### 3.4 Purchase price accounting (OURS, standard method)
Equity purchase price ≈ $26.5B. Write off Splunk's existing $1,417M goodwill;
**intangible step-up = $9.0B (OURS**, 10-yr life — Splunk's ~$3.7B revenue base
carries substantial developed-technology + customer-relationship intangibles);
DTL at **21%** statutory on the step-up. Goodwill is the plug. Because Splunk's
identifiable net assets are *negative* (−$110.5M equity, less $1,417M existing
goodwill written off), goodwill is large — most of the price is intangibles +
goodwill, exactly as expected for a high-growth software target bought at a 31%
premium to an already-rich multiple.

### 3.5 Synergies — BOTH cases OURS (proxy quantifies none)
Grounded in Splunk's ~$3.9B FY23 cost base: **Conservative $200M** (33/67/100%)
and **Base $400M** (50/75/100%) annual run-rate cost synergies. Breakeven-synergy
framing against these; no figure presented as management's.

### 3.6 Marginal tax = 16% (OURS) for pro forma adjustments; DTL 21% statutory.

## 4. Expected read (filled from engine output at the gate)
All-cash + a loss-making target ⇒ **heavily dilutive to Cisco EPS in the early
years** (Splunk's losses + ~$22B of after-tax interest, no offsetting new-share
denominator effect since it's all cash), narrowing as Splunk's margin ramps and
synergies phase in. This is the honest, correct result — and the mirror image of
a "stock-for-a-profitable-target" deal. Standalone Splunk DCF (ours) and the
Qatalyst/Morgan Stanley reproductions are computed at the gate. Numbers filled
in by `src/flagship_csco_splk.py` output.
