"""CSV / TSV / any delimited text. Falls back to line parsing if no header is found."""
from __future__ import annotations

import csv
import io

from ..models import ParsedRow
from ._decode import decode
from .tabular import parse_grid
from .text_parser import parse_text


def parse(data: bytes) -> list[ParsedRow]:
    text = decode(data)
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = "\t" if sample.count("\t") > sample.count(",") else ","
    grid = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    rows = parse_grid(grid)
    return rows if rows is not None else parse_text(text)
