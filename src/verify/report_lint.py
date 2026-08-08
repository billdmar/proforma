"""Report-number provenance lint (the report-lint gate).

The memo may render only numbers the engine produced — nothing hand-typed. The
challenge is that the memo displays engine magnitudes at many scales (billions
with 1 dp, per-share with 2 dp, percents, multiples), so a naive absolute-
tolerance comparison against raw engine floats is unsound.

Design: :func:`collect_engine_numbers` emits every engine value in the *display
forms* the memo could render it as — raw, in thousands/millions/billions, and as
a percent — each rounded to a small set of precisions. :func:`extract_report_numbers`
pulls the numeric tokens from the rendered HTML (ignoring inlined chart data).
:func:`lint_report_numbers` flags any rendered token that matches no engine
display-form within a tight absolute tolerance. This is sound (a foreign number
has no match) without being noisy on legitimately-scaled values.

Ported from the thesis project (cited in docs/DESIGN.md):
:func:`extract_report_numbers` and :func:`lint_report_numbers` are verbatim;
:func:`collect_engine_numbers` is rewritten to walk the merger
:class:`~src.interfaces.MergerModelBundle`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.interfaces import MergerModelBundle


@dataclass
class LintReport:
    """Result of :func:`lint_report_numbers`. ``passed`` iff every rendered
    number traces to an engine number in some display form."""

    numbers_checked: int = 0
    unsourced: list[float] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.unsourced

    def summary(self) -> str:
        head = f"Report-number lint: {self.numbers_checked} rendered numbers"
        return head + (" — PASS" if self.passed else f" — {len(self.unsourced)} UNSOURCED")


def lint_report_numbers(
    rendered_numbers: set[float],
    engine_numbers: set[float],
    abs_tol: float = 0.011,
) -> LintReport:
    """Flag rendered numbers with no engine source.

    ``engine_numbers`` already contains every engine value in its plausible
    display forms rounded to the report's precisions (see
    :func:`collect_engine_numbers`), so matching is near-exact: a rendered
    number is sourced only when an engine display-form is within ``abs_tol``
    (one display unit at 2 dp). A tight absolute band — NOT a relative one —
    keeps the check sound: a relative band creates near-continuous coverage in
    dense value regions and would spuriously "source" a fabricated number.
    """
    engine = sorted(engine_numbers)
    unsourced: list[float] = []
    for x in rendered_numbers:
        if not any(abs(x - e) <= abs_tol for e in engine):
            unsourced.append(x)
    return LintReport(numbers_checked=len(rendered_numbers), unsourced=unsourced)


_NUM_RE = re.compile(r"-?\d[\d,]*\.?\d*")


def extract_report_numbers(html: str, tables_only: bool = True) -> set[float]:
    """Pull numeric tokens from rendered report HTML.

    Scope (``tables_only``, default): only the financial EXHIBITS — the
    ``<table>`` elements — where every number must be an engine output. Narrative
    prose (``<p>``) legitimately cites contextual/sourced facts (52-week ranges,
    basis points, deal terms) that are the author's writing, not engine outputs,
    so it is out of scope for a machine number-lint. This makes the gate both
    sound and meaningful: "every number in every financial exhibit is verified."

    Strips base64 chart data, ISO dates, and FY labels (their digits are labels),
    then parses $-amounts, percents, multiples, and plain numbers to floats at
    their displayed magnitude; trivial tokens (0, small ints, years) are dropped.
    """
    if tables_only:
        html = " ".join(re.findall(r"<table.*?</table>", html, flags=re.DOTALL))
    text = re.sub(r"data:image/[^;]+;base64,[^\"']+", "", html)
    text = re.sub(r"\d{4}-\d{2}-\d{2}", " ", text)
    text = re.sub(r"FY\s*\d{2,4}E?", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    out: set[float] = set()
    for tok in _NUM_RE.findall(text):
        tok = tok.strip().rstrip(".")
        if not tok or tok in {"-"}:
            continue
        try:
            v = float(tok.replace(",", ""))
        except ValueError:
            continue
        # Exclude non-financial tokens: figure numbers, small counts, 4-digit
        # years, and bare 2-digit integers (FY-label remnants / list indices).
        if v == 0:
            continue
        if v.is_integer() and (abs(v) <= 40 or 2000 <= v <= 2035):
            continue
        out.add(round(v, 2))
    return out


# Disclosed deal facts the memo narrative may cite (sourced to the proxy / 8-Ks
# with provenance in DealTerms), which are legitimately not engine outputs. Kept
# as an allowlist mechanism so the lint stays strict on exhibit figures without
# flagging a handful of cited headline deal facts in prose. Empty by default: the
# flagship deal's disclosed figures (cash/share, exchange ratio, premium) all
# reappear as engine display-forms via ``collect_engine_numbers`` below.
NARRATIVE_SOURCED_FACTS: set[float] = set()


def collect_engine_numbers(model: MergerModelBundle) -> set[float]:
    """Gather every engine figure the memo may cite, in all display forms.

    Walks every number the merger deliverables could render — the consideration
    build, sources & uses, the PPA walk to goodwill, each synergy case's EPS
    bridge + accretion/(dilution) and contribution/ownership, the sensitivity
    grids + breakeven, the fairness differential ranges, and the precedent
    multiples. For each base magnitude we add the raw value, its thousands /
    millions / billions scalings and its ×100 percent form — each rounded to the
    precisions the memo templates use (and both signed and abs). The lint then
    matches rendered tokens against this set; a fabricated number has no engine
    display-form match.
    """
    base: set[float] = set()

    def add(*values: float | None) -> None:
        for v in values:
            if v is not None:
                base.add(float(v))

    # --- Consideration build ------------------------------------------------
    c = model.deal.consideration
    add(
        c.cash_per_share,
        c.stock_per_share_value,
        c.total_per_share,
        c.target_shares,
        c.aggregate_cash,
        c.aggregate_stock_value,
        c.equity_purchase_price,
        c.implied_premium_pct,
        c.exchange_ratio,
        c.new_shares_issued,
    )

    # --- Sources & uses -----------------------------------------------------
    su = model.deal.sources_and_uses
    add(*su.sources.values())
    add(*su.uses.values())
    add(su.total_sources, su.total_uses)

    # --- Purchase price allocation (the goodwill walk) ----------------------
    p = model.deal.ppa
    add(
        p.equity_purchase_price,
        p.target_book_equity,
        p.target_existing_goodwill,
        p.identifiable_net_assets_at_book,
        p.intangible_step_up,
        p.ppe_step_up,
        p.deferred_tax_liability,
        p.net_identifiable_assets,
        p.goodwill,
    )
    add(model.deal.incremental_da_annual)

    # --- Combination results: EPS bridge + contribution, every case --------
    for combo in model.combinations:
        for b in combo.eps_bridge:
            add(
                b.acquirer_standalone_ni,
                b.target_standalone_ni,
                b.incremental_interest_aftertax,
                b.foregone_interest_aftertax,
                b.incremental_da_aftertax,
                b.synergies_aftertax,
                b.pro_forma_net_income,
                b.acquirer_standalone_shares,
                b.new_shares_issued,
                b.pro_forma_shares,
                b.acquirer_standalone_eps,
                b.pro_forma_eps,
                b.accretion_dilution_pct,
            )
        con = combo.contribution
        add(
            con.acquirer_revenue,
            con.target_revenue,
            con.acquirer_ebitda,
            con.target_ebitda,
            con.acquirer_net_income,
            con.target_net_income,
            con.acquirer_ownership_pct,
            con.target_ownership_pct,
        )
        add(combo.synergy_case.run_rate_annual)

    # --- Sensitivities (grid cells + breakeven) -----------------------------
    if model.sensitivities is not None:
        s = model.sensitivities
        for grid in (s.premium_x_synergies, s.consideration_mix):
            add(*grid.row_values)
            add(*grid.col_values)
            for rowvals in grid.values:
                add(*rowvals)
        add(s.breakeven_synergies)

    # --- Fairness differential (disclosed vs. our reproduced ranges) --------
    if model.fairness_differential is not None:
        for rep in model.fairness_differential.reproductions:
            add(rep.disclosed_low, rep.disclosed_high, rep.our_low, rep.our_high, rep.overlap_pct)

    # --- Precedents (premiums / multiples table) ----------------------------
    for pt in model.precedents:
        add(pt.ev, pt.ev_revenue, pt.ev_ebitda)

    add(*NARRATIVE_SOURCED_FACTS)  # cited disclosed deal facts in prose

    # Expand each base value into its plausible display forms.
    forms: set[float] = set()
    for v in base:
        for scaled in (v, v / 1e3, v / 1e6, v / 1e9, v * 100.0):
            for dp in (0, 1, 2, 3, 4):
                forms.add(round(scaled, dp))
                forms.add(round(abs(scaled), dp))  # signed values rendered abs
    return forms
