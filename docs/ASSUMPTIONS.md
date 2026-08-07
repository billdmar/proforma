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

## 3. Our modeling assumptions (OURS — set by ORCH at W2)
_To be filled at W2 with 2–4 line rationales each: standalone drivers for both
companies; financing structure (new debt / rate / cash used / fees); PPA choices
(step-ups, useful lives, deferred-tax rate); and TWO synergy cases —
management's disclosed figure (quoted + sourced) and our conservative case
(reasoned). Placeholder now; the judgment core is written when the real-deal
model is built._
