# DESIGN.md — proforma architecture

_Status: complete. The full pipeline (EDGAR extraction → dual standalone models →
deal engine → combination engine → workbook + memo + verification) is built and
green in CI: 260 tests, 97.7% coverage, dual XBRL tie-out (1,728 lines to the
dollar), Excel↔Python differential (61 cells to the cent), fairness differential
(67.3% mean overlap), determinism. See README for the recruiter summary._

## One-line
A merger-model platform that reconstructs one real announced US public-public
deal (**Synopsys / ANSYS**) from SEC filings, computes every number in a Python
engine, expresses it as a **live-formula Excel model**, renders an **M&A
committee memo PDF**, and verifies itself against the deal's own **disclosed
fairness-opinion analyses**.

## Single source of truth
The engine builds one `MergerModelBundle` (`src/interfaces.py`). The workbook
writer expresses it as formulas, the memo renders it, and the verifier diffs the
recalculated workbook against it to the cent. Nothing is hand-typed into either
deliverable.

## Pipeline
```
EDGAR (XBRL CompanyFacts + proxy/S-4/8-K text)
   │  src/edgar  → NormalizedFacts (both companies) + DealTerms + FairnessDisclosure
   ▼
Standalone models (src/standalone)  ── driver-based projections, both companies
   ▼
Deal engine (src/deal)  ── consideration, sources & uses, purchase price accounting → goodwill
   ▼
Combination engine (src/combine)  ── pro forma IS/BS, EPS bridge, accretion/dilution, contribution
   ▼
   ├─ Workbook (src/workbook)   live-formula .xlsx
   ├─ Memo (src/report)         WeasyPrint PDF
   ├─ Sensitivities (src/scenarios)   premium×synergies, mix, breakeven
   ├─ Precedents (src/precedents)     curated premiums-paid table, cited
   └─ Fairness differential (src/fairness)  advisors' disclosed ranges → our engine
   ▼
Verify (src/verify)  ── XBRL tie-out · Excel↔Python cell differential · deal invariants
                        · sensitivity monotonicity · fairness overlap · report lint · determinism
```

## Reuse from the thesis project (cited, not blind-imported)
proforma is the sibling of `thesis` (single-company valuation). Reused
near-verbatim, with the retargeting noted here:
- **`src/schema.py`** — the `NormalizedFacts` contract (LineItem / Period /
  Provenance / Fact, restatement resolution, honest-unknown accessors). Extended
  with the merger-specific `DealTerms`, `FairnessDisclosure`, and `DocProvenance`
  (document-level provenance for proxy/8-K text, distinct from XBRL-fact provenance).
- **`src/interfaces.py`** — dataclasses + `typing.Protocol` engine seams; the
  single-company engines (statement builder, DCF, comps, LBO) are reused because
  the fairness differential runs advisors' disclosed assumptions through them.
  New: deal engine, combination engine, sensitivities, fairness differential,
  and `MergerModelBundle`.
- **`config/settings.py`** — SEC fair-access scaffolding (`PROFORMA_OFFLINE`).
- **EDGAR client, statement builder (W1); valuation/comps engines (W2); verify
  suite (invariants/audit/tieout/report_lint) and report template/charts (W2–W3);
  workbook styles + writer patterns (W1); CI, `verify_all.sh`, docs templates** —
  ported from thesis with merger-specific extensions and cited here.

Net-new for the merger model: proxy/8-K **document-text retrieval** with
document-level provenance; the deal engine (S&U, PPA→goodwill, financing); the
combination engine (pro forma statements, EPS bridge, A/D, contribution); the
fairness differential harness; the precedents table; and the memo.

## Contracts frozen at W0 (ORCH-only afterward)
`src/schema.py` (+ DealTerms, FairnessDisclosure), `src/interfaces.py`
(engine protocols + MergerModelBundle), `docs/WORKBOOK_SPEC.md`,
`docs/MEMO_SPEC.md`. See those files for the authoritative shapes.
