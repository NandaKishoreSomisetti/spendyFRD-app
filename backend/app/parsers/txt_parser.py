"""Plain text: try it as a delimited table first, then line-by-line."""
from __future__ import annotations

from ..models import ParsedRow
from . import csv_parser


def parse(data: bytes) -> list[ParsedRow]:
    return csv_parser.parse(data)
