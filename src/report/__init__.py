"""M&A committee memo rendering — WeasyPrint PDF from the MergerModelBundle."""

from __future__ import annotations

from src.report.charts import build_all_charts
from src.report.render import render_memo
from src.report.template import build_html

__all__ = ["build_all_charts", "build_html", "render_memo"]
