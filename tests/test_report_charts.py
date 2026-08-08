"""Tests for the memo chart suite (src/report/charts.py).

Builds the real flagship bundle once, renders all charts headless (Agg), and
asserts each expected PNG exists and is non-empty. Also exercises the
individual builders' guard branches (missing sensitivities / fairness) so the
degenerate paths render rather than crash.
"""

from __future__ import annotations

import os

import pytest
from src.flagship import build_flagship_bundle
from src.report import charts as ch

_PRECEDENTS_CSV = "data/curated/precedents_software.csv"

_EXPECTED = [
    "sources_uses",
    "ppa_waterfall",
    "accretion_by_year",
    "premium_synergies_heatmap",
    "contribution_ownership",
    "target_football",
    "fairness_football",
]


@pytest.fixture(scope="module")
def bundle():
    return build_flagship_bundle(_PRECEDENTS_CSV)


def test_build_all_charts_returns_expected_pngs(bundle, tmp_path):
    out = str(tmp_path / "assets")
    result = ch.build_all_charts(bundle, out)
    assert set(result) == set(_EXPECTED)
    for name, path in result.items():
        assert os.path.exists(path), name
        assert os.path.getsize(path) > 0, name
        assert path.endswith(".png")


def test_charts_render_headless_deterministic_names(bundle, tmp_path):
    # No display needed (Agg backend); each builder writes a stable file name.
    out = str(tmp_path / "a")
    p1 = ch.sources_uses_chart(bundle, out)
    p2 = ch.ppa_waterfall_chart(bundle, out)
    assert p1.endswith("sources_uses.png")
    assert p2.endswith("ppa_waterfall.png")


def test_heatmap_guard_when_no_sensitivities(tmp_path):
    # Own bundle so the mutation doesn't leak into the module-scoped fixture.
    b = build_flagship_bundle(_PRECEDENTS_CSV, with_sensitivities=False)
    assert b.sensitivities is None
    p = ch.premium_synergies_heatmap(b, str(tmp_path))
    assert os.path.getsize(p) > 0


def test_footballs_guard_when_no_fairness_or_dcf(tmp_path):
    b = build_flagship_bundle(_PRECEDENTS_CSV, with_fairness=False)
    b.target_dcf = None
    tf = ch.target_football_chart(b, str(tmp_path))
    ff = ch.fairness_football_chart(b, str(tmp_path))
    assert os.path.getsize(tf) > 0
    assert os.path.getsize(ff) > 0
