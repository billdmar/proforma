"""Matplotlib chart suite for the M&A committee memo.

Every chart is driven exclusively from a :class:`~src.interfaces.MergerModelBundle`;
no financial figure is hand-typed here (single-source-of-truth rule). Each
function saves a PNG into a caller-supplied directory and returns its path.

House style: restrained navy/steel palette, serif titles, sans tick labels, no
chart junk. Uses the non-interactive Agg backend so it renders headless in CI
and inside the WeasyPrint pipeline.

Ported from the thesis project (cited in docs/DESIGN.md): the
``matplotlib.use("Agg")``-before-pyplot block, the palette constants, ``_STYLE``
and ``_save`` are reused verbatim; the individual charts are rewritten to the
deal exhibits (sources & uses, PPA waterfall, accretion/dilution, the
premium×synergies heatmap, contribution vs. ownership, and the fairness /
target-valuation football fields, the last reusing the thesis football-field
structure).
"""

from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402  (must follow use("Agg"))

from src.interfaces import MergerModelBundle  # noqa: E402

# --- House style ---------------------------------------------------------
ACCENT = "#1f3b57"  # deep navy — acquirer / primary
STEEL = "#5b7c99"  # secondary series / target
MUTED = "#9aa7b1"  # neutral
GRID = "#d8dee3"
POSITIVE = "#2f6f4f"  # accretion / offer marker
NEGATIVE = "#a3322b"  # dilution
FIGSIZE = (7.2, 3.9)
DPI = 150

_STYLE = {
    "figure.dpi": DPI,
    "savefig.dpi": DPI,
    "axes.edgecolor": "#6b7680",
    "axes.linewidth": 0.8,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.6,
    "axes.titlesize": 12,
    "axes.titleweight": "bold",
    "axes.titlecolor": ACCENT,
    "font.family": "sans-serif",
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
}


def _save(fig: plt.Figure, out_dir: str, name: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, name)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


def _bridge_year_labels(model: MergerModelBundle) -> list[str]:
    """FYxx labels for the projection years, from the primary combination's bridge."""
    out: list[str] = []
    for b in model.primary_combination().eps_bridge:
        p = b.year
        fy = p.fy if p.fy is not None else p.end.year
        out.append(f"FY{str(fy)[-2:]}")
    return out


# --- Charts --------------------------------------------------------------
def sources_uses_chart(model: MergerModelBundle, out_dir: str) -> str:
    """Two stacked bars — total sources and total uses of funds — that must tie.

    Each bar stacks its keyed legs (new debt / cash / stock issued vs. equity
    purchase price / refinanced debt / fees), so the eye sees both the funding
    mix and that the columns reach the same height (sources = uses)."""
    su = model.deal.sources_and_uses
    scale = 1e9
    colors = [ACCENT, STEEL, MUTED, "#c2cbd3", "#7a8894"]
    with plt.rc_context(_STYLE):
        fig, ax = plt.subplots(figsize=FIGSIZE)
        ax.grid(False)
        ax.yaxis.grid(True)
        for col, legs in enumerate([su.sources, su.uses]):
            bottom = 0.0
            ci = 0
            for name, val in legs.items():
                if not val:
                    continue
                v = val / scale
                ax.bar(col, v, bottom=bottom, color=colors[ci % len(colors)], width=0.5, zorder=2)
                if v > 0.4:  # label only legibly-tall segments
                    ax.text(
                        col,
                        bottom + v / 2,
                        name.replace("_", " "),
                        ha="center",
                        va="center",
                        fontsize=6.5,
                        color="white",
                    )
                bottom += v
                ci += 1
            ax.text(col, bottom, f"${bottom:,.1f}B", ha="center", va="bottom", fontsize=8)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["Sources", "Uses"])
        ax.set_ylabel("$ bn")
        ax.margins(y=0.15)
        ax.set_title("Sources & Uses of Funds (must tie)")
    return _save(fig, out_dir, "sources_uses.png")


def ppa_waterfall_chart(model: MergerModelBundle, out_dir: str) -> str:
    """Waterfall from equity purchase price down through net identifiable assets
    (book net assets + step-ups − DTL) to the goodwill plug."""
    p = model.deal.ppa
    scale = 1e9
    epp = p.equity_purchase_price / scale
    net_id = p.net_identifiable_assets / scale
    goodwill = p.goodwill / scale
    with plt.rc_context(_STYLE):
        fig, ax = plt.subplots(figsize=FIGSIZE)
        ax.grid(False)
        ax.yaxis.grid(True)
        # Bar 1: equity purchase price. Bar 2: less net identifiable assets
        # (floats down from EPP). Bar 3: goodwill (the residual plug).
        ax.bar(0, epp, color=ACCENT, width=0.6, zorder=2)
        ax.bar(1, net_id, bottom=epp - net_id, color=STEEL, width=0.6, zorder=2)
        ax.bar(2, goodwill, color=POSITIVE, width=0.6, zorder=2)
        ax.set_xticks([0, 1, 2])
        ax.set_xticklabels(
            ["Equity\npurchase price", "less: net\nidentifiable assets", "Goodwill\n(plug)"]
        )
        ax.set_ylabel("$ bn")
        for xi, val in [(0, epp), (2, goodwill)]:
            ax.text(xi, val, f"${val:,.1f}B", ha="center", va="bottom", fontsize=8)
        ax.text(1, epp, f"(${net_id:,.1f}B)", ha="center", va="bottom", fontsize=8, color=STEEL)
        ax.margins(y=0.18)
        ax.set_title("Purchase Price Allocation — Goodwill Walk")
    return _save(fig, out_dir, "ppa_waterfall.png")


def accretion_chart(model: MergerModelBundle, out_dir: str) -> str:
    """Grouped bars of accretion/(dilution) % by projected year, one series per
    synergy case. Dilution bars are red, accretion green."""
    labels = _bridge_year_labels(model)
    cases = model.combinations
    n_years = len(labels)
    with plt.rc_context(_STYLE):
        fig, ax = plt.subplots(figsize=FIGSIZE)
        ax.grid(False)
        ax.yaxis.grid(True)
        width = 0.8 / max(1, len(cases))
        x = range(n_years)
        for ci, combo in enumerate(cases):
            ad = combo.accretion_by_year()
            vals = [(v * 100.0) if v is not None else 0.0 for v in ad]
            offs = [i + ci * width - 0.4 + width / 2 for i in x]
            base_color = ACCENT if ci == 0 else STEEL
            colors = [base_color if v >= 0 else NEGATIVE for v in vals]
            ax.bar(offs, vals, width=width, color=colors, zorder=2, label=combo.synergy_case.name)
        ax.axhline(0, color="#6b7680", linewidth=0.9)
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels)
        ax.set_ylabel("Accretion / (dilution) %")
        ax.legend(loc="lower right", fontsize=7, frameon=False)
        ax.set_title("EPS Accretion / (Dilution) by Year — both synergy cases")
    return _save(fig, out_dir, "accretion_by_year.png")


def premium_synergies_heatmap(model: MergerModelBundle, out_dir: str) -> str:
    """Heatmap of Year-N accretion/(dilution) % across premium × synergies."""
    s = model.sensitivities
    if s is None:
        with plt.rc_context(_STYLE):
            fig, ax = plt.subplots(figsize=FIGSIZE)
            ax.text(
                0.5,
                0.5,
                "No sensitivities available",
                ha="center",
                va="center",
                transform=ax.transAxes,
                color=MUTED,
                fontsize=10,
            )
            ax.set_xticks([])
            ax.set_yticks([])
            return _save(fig, out_dir, "premium_synergies_heatmap.png")
    g = s.premium_x_synergies
    grid = [[(v * 100.0) if v is not None else float("nan") for v in row] for row in g.values]
    with plt.rc_context(_STYLE):
        fig, ax = plt.subplots(figsize=FIGSIZE)
        ax.grid(False)
        im = ax.imshow(grid, cmap="RdYlGn", aspect="auto", origin="lower")
        ax.set_xticks(range(len(g.col_values)))
        ax.set_xticklabels([f"${v / 1e9:,.1f}B" for v in g.col_values])
        ax.set_yticks(range(len(g.row_values)))
        ax.set_yticklabels([f"{v * 100:.0f}%" for v in g.row_values])
        ax.set_xlabel(g.col_label.replace("_", " ").title())
        ax.set_ylabel(g.row_label.replace("_", " ").title())
        for i, row in enumerate(grid):
            for j, v in enumerate(row):
                if v == v:  # not NaN
                    ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=7, color="#1c2429")
        fig.colorbar(im, ax=ax, shrink=0.8, label="A/(D) %")
        ax.set_title(f"Year-{g.year_idx + 1} A/(D): Premium × Synergies")
    return _save(fig, out_dir, "premium_synergies_heatmap.png")


def contribution_ownership_chart(model: MergerModelBundle, out_dir: str) -> str:
    """Stacked 100%-bars comparing each party's contribution to combined revenue,
    EBITDA and net income against its pro forma ownership of the combined entity."""
    con = model.primary_combination().contribution

    def split(a: float, t: float) -> tuple[float, float]:
        tot = a + t
        return (a / tot, t / tot) if tot else (0.0, 0.0)

    cats = ["Revenue", "EBITDA", "Net income", "Ownership"]
    acq_share = [
        split(con.acquirer_revenue, con.target_revenue)[0],
        split(con.acquirer_ebitda, con.target_ebitda)[0],
        split(con.acquirer_net_income, con.target_net_income)[0],
        con.acquirer_ownership_pct,
    ]
    tgt_share = [1.0 - a for a in acq_share]
    with plt.rc_context(_STYLE):
        fig, ax = plt.subplots(figsize=FIGSIZE)
        ax.grid(False)
        ax.yaxis.grid(True)
        x = range(len(cats))
        acq_pct = [v * 100 for v in acq_share]
        tgt_pct = [v * 100 for v in tgt_share]
        ax.bar(x, acq_pct, color=ACCENT, width=0.6, label=model.acquirer.ticker, zorder=2)
        ax.bar(
            x, tgt_pct, bottom=acq_pct, color=STEEL, width=0.6, label=model.target.ticker, zorder=2
        )
        for i in x:
            ax.text(
                i,
                acq_pct[i] / 2,
                f"{acq_pct[i]:.0f}%",
                ha="center",
                va="center",
                fontsize=7,
                color="white",
            )
            ax.text(
                i,
                acq_pct[i] + tgt_pct[i] / 2,
                f"{tgt_pct[i]:.0f}%",
                ha="center",
                va="center",
                fontsize=7,
                color="white",
            )
        ax.set_xticks(list(x))
        ax.set_xticklabels(cats)
        ax.set_ylabel("% of combined")
        ax.set_ylim(0, 100)
        ax.legend(loc="upper right", fontsize=7, frameon=False, ncol=2)
        ax.set_title("Contribution vs. Pro Forma Ownership")
    return _save(fig, out_dir, "contribution_ownership.png")


def _football(
    rows: list[tuple[str, float, float]], offer: float | None, title: str, out_dir: str, name: str
) -> str:
    """Shared horizontal valuation-range renderer (thesis football-field template).

    ``rows`` is (label, low, high); ``offer`` draws the offered-consideration
    reference line."""
    with plt.rc_context(_STYLE):
        fig, ax = plt.subplots(figsize=(7.2, 2.6 + 0.35 * max(1, len(rows))))
        ax.grid(False)
        ax.xaxis.grid(True)
        labels = [r[0] for r in rows]
        for i, (_, lo, hi) in enumerate(rows):
            ax.barh(i, hi - lo, left=lo, height=0.45, color=STEEL, zorder=2)
            ax.text(lo, i, f"${lo:,.0f}", va="center", ha="right", fontsize=7, color="#4a545c")
            ax.text(hi, i, f"${hi:,.0f}", va="center", ha="left", fontsize=7, color="#4a545c")
        ax.set_yticks(range(len(rows)))
        ax.set_yticklabels(labels)
        ax.set_xlabel("Implied share price (USD)")
        if offer is not None:
            ax.axvline(offer, color=POSITIVE, linewidth=1.6)
            ax.text(
                offer,
                -0.6,
                f"Offer ${offer:,.0f}",
                color=POSITIVE,
                fontsize=7.5,
                fontweight="bold",
                ha="center",
            )
        ax.set_ylim(-0.9, len(rows) - 0.2)
        ax.invert_yaxis()
        ax.set_title(title)
    return _save(fig, out_dir, name)


def target_football_chart(model: MergerModelBundle, out_dir: str) -> str:
    """Standalone-ANSYS valuation ranges (our DCF, comps/precedents cross-checks)
    against the offered per-share consideration."""
    rows: list[tuple[str, float, float]] = []
    d = model.target_dcf
    if d is not None:
        lo = min(d.implied_price_gordon, d.implied_price_exit)
        hi = max(d.implied_price_gordon, d.implied_price_exit)
        rows.append(("Our DCF (Gordon / Exit)", lo, hi))
    # Comps cross-check: reuse the advisor's disclosed multiple-based reproduction
    # (Selected Companies / Transactions), which we reproduced through our engine.
    if model.fairness_differential is not None:
        for rep in model.fairness_differential.reproductions:
            if "Companies" in rep.method and rep.our_low is not None and rep.our_high is not None:
                rows.append(("Comps (our reproduction)", rep.our_low, rep.our_high))
                break
    offer = model.deal.consideration.total_per_share
    if not rows:  # degenerate guard so the exhibit still renders
        rows.append(("Offer", offer, offer))
    return _football(
        rows, offer, "Target Valuation vs. Offer — ANSYS standalone", out_dir, "target_football.png"
    )


def fairness_football_chart(model: MergerModelBundle, out_dir: str) -> str:
    """The differential: advisor-disclosed implied ranges vs. our reproduction,
    per methodology, against the offered consideration."""
    fd = model.fairness_differential
    rows: list[tuple[str, float, float]] = []
    if fd is not None:
        for rep in fd.reproductions:
            if rep.disclosed_low is not None and rep.disclosed_high is not None:
                rows.append((f"{rep.method} (disclosed)", rep.disclosed_low, rep.disclosed_high))
            if rep.our_low is not None and rep.our_high is not None:
                rows.append((f"{rep.method} (ours)", rep.our_low, rep.our_high))
    offer = model.deal.consideration.total_per_share
    if not rows:
        rows.append(("Offer", offer, offer))
    return _football(
        rows,
        offer,
        "Fairness Differential — disclosed vs. reproduced",
        out_dir,
        "fairness_football.png",
    )


def build_all_charts(model: MergerModelBundle, out_dir: str) -> dict[str, str]:
    """Render the full suite; returns a name -> path map for the template."""
    return {
        "sources_uses": sources_uses_chart(model, out_dir),
        "ppa_waterfall": ppa_waterfall_chart(model, out_dir),
        "accretion_by_year": accretion_chart(model, out_dir),
        "premium_synergies_heatmap": premium_synergies_heatmap(model, out_dir),
        "contribution_ownership": contribution_ownership_chart(model, out_dir),
        "target_football": target_football_chart(model, out_dir),
        "fairness_football": fairness_football_chart(model, out_dir),
    }
