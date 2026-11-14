"""Excel .xlsx / .xlsm: every sheet is scanned for a transaction table."""
from __future__ import annotations

import io

from openpyxl import load_workbook

from ..models import ParsedRow
from .tabular import parse_grid
from .text_parser import parse_text


def parse(data: bytes) -> list[ParsedRow]:
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    rows: list[ParsedRow] = []
    fallback_text: list[str] = []
    try:
        for sheet in wb.worksheets:
            grid = [list(r) for r in sheet.iter_rows(values_only=True)]
            parsed = parse_grid(grid)
            if parsed is not None:
                rows.extend(parsed)
            else:
                fallback_text.extend(
                    "  ".join(str(c) for c in r if c not in (None, "")) for r in grid
                )
    finally:
        wb.close()
    if not rows and fallback_text:
        rows = parse_text("\n".join(fallback_text))
    return rows
