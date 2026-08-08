# RESUME_BULLETS.md — proforma (real figures, for IB/M&A applications)

Figures are the engine's outputs as of the current build (see `docs/ASSUMPTIONS.md`
§4–5). Repo: https://github.com/billdmar/proforma · Deliverables in `releases/`.

## Primary (3 bullets — the default)
- Reconstructed **Synopsys's ~$34B acquisition of ANSYS** from the actual SEC
  merger proxy into a **live-formula Excel merger model and a 9-section M&A
  committee memo** — sources & uses, purchase price accounting (**$25.4B
  goodwill** on an $8B intangible step-up), pro forma statements, and EPS
  **accretion/(dilution) of −38.5% / −31.4% / −25.6% (Yr 1–3)** with
  premium×synergies and consideration-mix sensitivities and a **~$1.25B
  breakeven-synergy** analysis.
- Verified the mechanics with a **dual-implementation differential matching 61
  workbook cells to the cent** against a Python engine, **dual-company XBRL
  tie-outs (1,728 statement lines reconciled to SEC facts to the dollar)**, a
  full set of deal invariants (sources = uses, goodwill/PPA tie, pro forma
  balance, independent EPS recompute), and **97.7% test coverage across 260
  tests in CI**.
- **Differentially validated the model against the deal's disclosed fairness
  opinion** — reproducing financial advisor Qatalyst Partners' implied valuation
  ranges from their own disclosed assumptions with **67.3% mean overlap**
  (79% on comps), every extracted figure provenance-stamped to its SEC
  accession.

## Finance-first (2 bullets — lead with the read, then the moat)
- Built a full **accretion/dilution merger model** on a real ~$35B software deal
  and showed it is **GAAP-dilutive but strategically underwritten** — a
  standalone DCF of the target (~$140–$264/share) well below the **$390/share**
  offer, with breakeven synergies (~$1.25B/yr) far above plausible cost savings,
  quantifying that the ~29% premium is paid for control and revenue synergy, not
  standalone value.
- Backed the call with an engineering moat: engine-vs-Excel cell differential to
  the cent, dual XBRL tie-outs, and a **reproduction of the banker's own
  fairness-opinion ranges from their disclosed inputs** — all green in CI at
  97.7% coverage.

## One-line (when space is tight)
- Reconstructed Synopsys/ANSYS (~$35B) from SEC filings into a verified
  live-formula merger model + M&A memo, with EPS accretion/dilution,
  sensitivities, and a fairness-opinion differential (67.3% range reproduction).

## LinkedIn Featured blurb (~50 words)
> proforma rebuilds Synopsys's ~$34B acquisition of ANSYS from the actual SEC
> merger proxy — a live-formula Excel model + M&A committee memo covering
> purchase accounting, pro forma EPS accretion/dilution, and sensitivities —
> then reproduces the banker's disclosed fairness-opinion ranges from their own
> assumptions. Every number engine-verified in CI.

## Talking points if asked to expand
- Why the deal is GAAP-dilutive (step-up amortization ~$0.8B/yr) yet defensible
  on cash EPS and strategy — the "silicon-to-systems" design stack.
- Cash-vs-stock accretion intuition (earnings yield vs. after-tax cost of debt).
- How goodwill falls out of the PPA walk; the deferred-tax liability on step-ups.
- What a fairness opinion does and doesn't tell you — and how I reproduced one.
- The verification moat: dual XBRL tie-out, Excel↔Python differential, invariants,
  determinism, report-lint (no hand-typed numbers), 97.7% coverage in CI.

## Stack
Python 3.12 engine (SEC XBRL + proxy extraction, provenance-stamped) → live-formula
Excel (openpyxl) + memo PDF (WeasyPrint) → verification suite (`formulas`-library
recalc differential, XBRL tie-out, accounting invariants, report-lint, determinism),
all green in GitHub Actions on committed fixtures.
