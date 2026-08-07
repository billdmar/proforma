# MEMO_SPEC.md — the M&A committee memo (frozen at W0, ORCH-owned)

The memo (`out/SNPS_ANSS_deal_memo.pdf`, 10–18 pp) is rendered by
`src/report/` (WeasyPrint, Jinja-free f-string template + matplotlib-`Agg`
charts, reusing the thesis pattern). **Every number is engine-generated** from
the `MergerModelBundle`; the report-lint gate (`src/verify/report_lint.py`)
scans all `<table>` exhibits and flags any figure with no engine display-form
match. Prose carries the analyst's words (ORCH-written); numeric claims live in
tables so they are lint-verifiable. The renderer sets
`DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` before importing weasyprint
(macOS; inert on CI).

## Voice & provenance discipline
- **Disclosed facts vs. our commentary are always labeled.** Deal terms, the
  advisors' analyses, management's projections and synergy figure are quoted
  with SEC provenance (accession + section). Our modeling choices and
  conservative synergy case are explicitly "our assumption."
- The owner must be able to deliver every paragraph aloud in an interview.

## Section order
1. **Deal overview & timeline** — parties, structure, consideration, premium,
   announce/close dates; sourced to the 8-Ks / press releases.
2. **Strategic rationale** — the disclosed rationale (with provenance) followed
   by our clearly-labeled commentary.
3. **Target valuation** — DCF / comps / precedents on ANSYS (thesis-style),
   framed against the offered consideration.
4. **Structure & financing** — cash/stock mix, new debt, fees, sources & uses.
5. **Purchase price accounting** — equity purchase price → goodwill walk;
   step-ups and their incremental D&A / deferred-tax effects.
6. **Accretion/dilution analysis** — the EPS bridge and A/D across years and
   both synergy cases; the premium × synergies and consideration-mix sensitivity
   story; why Year-1 dilution is not automatically bad.
7. **Synergies** — management's disclosed figure (quoted, sourced) vs. our
   conservative case (reasoned); breakeven-synergy framing. Both labeled
   assumptions — never presented as fact.
8. **Risks** — regulatory (antitrust), integration, financing, market.
9. **Fairness-opinion comparison appendix** — the differential: advisors'
   disclosed implied ranges vs. our reproduction from their disclosed
   assumptions; overlap quantified; deviations explained.

## Mandatory disclaimer (front matter + footer)
> Educational reconstruction from public SEC filings. Not investment advice.
> Synergy figures are labeled assumptions (management's disclosed estimate and
> our own conservative case), not forecasts. This memo passes no verdict on
> whether the transaction should occur and implies no endorsement by the SEC,
> the named companies, or their financial advisors.
