"""PDF: extract tables first (most bank statements); fall back to layout text."""
from __future__ import annotations

import io

import pdfplumber

from ..models import ParsedRow
from .tabular import parse_grid
from .text_parser import parse_text


class EmptyPDF(ValueError):
    pass


def parse(data: bytes) -> list[ParsedRow]:
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        # Tables often continue across pages without repeating the header,
        # so collect every table row into one grid.
        grid: list[list[object]] = []
        text_parts: list[str] = []
        for page in pdf.pages:
            for table in page.extract_tables():
                grid.extend(table)
            text_parts.append(page.extract_text(layout=False) or "")

    if grid:
        rows = parse_grid(grid)
        if rows:
            return rows

    text = "\n".join(text_parts)
    if not text.strip():
        raise EmptyPDF("This PDF has no selectable text (it may be a scan). Try an image/OCR upload.")
    return parse_text(text)
