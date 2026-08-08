"""Cache computed values into a live-formula workbook without removing formulas.

Problem this solves (a recruiter-surface polish, not a modelling change): the
:class:`~src.workbook.writer.ExcelWorkbookWriter` emits a genuinely *live-formula*
``.xlsx`` — every computed cell is an Excel formula, no hardcodes — but openpyxl
writes NO cached formula result. Desktop Excel recalculates on open
(``fullCalcOnLoad``), so it looks right there; but every *previewer* that does
not run a recalc engine — GitHub's in-browser xlsx view, macOS Quick Look,
Google Sheets import, ``openpyxl.load_workbook(path, data_only=True)`` — reads
the empty cached slot and shows BLANK for the headline Cover tearsheet and every
Deal/PPA/Pro-Forma formula cell. The model reads as hollow.

The fix is a post-process pass that writes each formula cell's *computed* value
into its cached-value slot so both readings coexist:

* ``data_only=False`` still returns the live formula string (unchanged);
* ``data_only=True`` now returns the number.

How the value is obtained: we recalculate the just-written file with the
``formulas`` library — the SAME engine the differential verifier uses in
``tests/test_workbook_writer.py`` and ``tests/test_integration_synthetic.py``, so
the cached numbers are exactly the differential-verified numbers, to the cent.

How the value is injected: openpyxl's public ``cell.value`` holds a formula OR a
value, never both, so there is no clean API path to a cached result. We therefore
edit the worksheet XML directly. Every formula cell openpyxl writes has the shape
``<c r="B7" s="4"><f>...</f><v /></c>`` — an empty ``<v/>`` placeholder already
sits after the formula. We replace that placeholder with ``<v>computed</v>``,
touching nothing else (the ``<f>`` formula element is left byte-for-byte intact).

Determinism: the zip is re-written through the same pinned-timestamp technique as
the writer's ``_save_pinned`` (fixed ``date_time`` on every entry, preserved
entry order), so two runs produce a byte-identical file.
"""

from __future__ import annotations

import os
import re
from html import unescape

import formulas

# ``<c r="COORD" ...>INNER</c>`` — INNER captured non-greedily. Literal ``<`` /
# ``>`` inside a formula are XML-escaped (``&lt;`` / ``&gt;``) by openpyxl, so
# the only ``</c>`` in range is the real cell close.
_CELL_RE = re.compile(r'<c r="([A-Z]+\d+)"([^>]*)>(.*?)</c>', re.DOTALL)
# The pinned epoch the writer uses (docProps + every zip entry) — keep in lockstep.
_FIXED_DATE_TIME = (2026, 1, 1, 0, 0, 0)


def cache_formula_values(path: str) -> None:
    """Inject each formula cell's recalculated value as its cached value, in place.

    Recalculates ``path`` with the ``formulas`` library and rewrites the file so
    that ``load_workbook(path, data_only=True)`` returns numbers for the formula
    cells while ``data_only=False`` still returns the live formulas. Deterministic:
    re-running on the same input yields a byte-identical file.
    """
    from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

    base = os.path.basename(path)
    solution = formulas.ExcelModel().loads(path).finish().calculate()

    with ZipFile(path, "r") as zin:
        infos = zin.infolist()
        raw = {info.filename: zin.read(info.filename) for info in infos}

    sheet_by_file = _sheet_names_by_worksheet_file(raw)

    updated: dict[str, bytes] = {}
    for name, filename in sheet_by_file.items():
        xml = raw[filename].decode("utf-8")
        new_xml = _inject_sheet(xml, name, solution, base)
        if new_xml != xml:
            updated[filename] = new_xml.encode("utf-8")

    # Rewrite the archive with pinned timestamps, preserving entry order so the
    # rebuild is byte-identical (mirrors ExcelWorkbookWriter._save_pinned).
    with ZipFile(path, "w", ZIP_DEFLATED, allowZip64=True) as zout:
        for info in infos:
            data = updated.get(info.filename, raw[info.filename])
            zinfo = ZipInfo(info.filename, date_time=_FIXED_DATE_TIME)
            zinfo.compress_type = ZIP_DEFLATED
            zout.writestr(zinfo, data)


def _sheet_names_by_worksheet_file(raw: dict[str, bytes]) -> dict[str, str]:
    """Map each sheet display name to its ``xl/worksheets/sheetN.xml`` entry.

    Resolves ``workbook.xml`` sheet ``r:id`` → ``workbook.xml.rels`` target, the
    same indirection Excel uses, so the mapping is robust to sheet ordering.
    """
    wbxml = raw["xl/workbook.xml"].decode("utf-8")
    relsxml = raw["xl/_rels/workbook.xml.rels"].decode("utf-8")

    name_to_rid = {
        unescape(name): rid
        for name, rid in re.findall(r'<sheet name="([^"]+)"[^>]*r:id="([^"]+)"', wbxml)
    }
    rid_to_target = {
        rid: target for target, rid in re.findall(r'Target="([^"]+)"[^>]*Id="([^"]+)"', relsxml)
    }

    mapping: dict[str, str] = {}
    for name, rid in name_to_rid.items():
        target = rid_to_target[rid]
        # Targets are e.g. "/xl/worksheets/sheet1.xml" or "worksheets/sheet1.xml".
        rel = target.split("/xl/", 1)[-1] if "/xl/" in target else target.lstrip("/")
        filename = rel if rel.startswith("xl/") else f"xl/{rel}"
        mapping[name] = filename
    return mapping


def _inject_sheet(xml: str, sheet_name: str, solution, base: str) -> str:
    """Return ``xml`` with each formula cell's ``<v/>`` filled with its recalc value."""
    prefix = f"'[{base}]{sheet_name.upper()}'!"

    def _repl(match: re.Match) -> str:
        coord, attrs, inner = match.group(1), match.group(2), match.group(3)
        if "<f" not in inner:
            return match.group(0)
        node = solution.get(f"{prefix}{coord}")
        if node is None:
            return match.group(0)
        value = node.value[0, 0]
        # Only numeric formula results are cached; the workbook has no string/error
        # formula cells, and a non-numeric slip should surface, not be masked.
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return match.group(0)
        # Keep the formula element verbatim; replace whatever <v> slot follows it.
        formula_element = inner.split("</f>", 1)[0] + "</f>"
        new_inner = f"{formula_element}<v>{_fmt(float(value))}</v>"
        return f'<c r="{coord}"{attrs}>{new_inner}</c>'

    return _CELL_RE.sub(_repl, xml)


def _fmt(value: float) -> str:
    """Shortest round-trip decimal string for a cached numeric value.

    ``repr`` gives the shortest string that round-trips to the same float in
    Python 3, so it is both precise and deterministic across runs/platforms.
    """
    return repr(value)
