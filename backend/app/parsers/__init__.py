"""Parser registry: picks a parser by file extension (with a magic-byte check for PDFs).

Every parser takes raw bytes and returns list[ParsedRow].
To support a new format, add a module with `parse(data: bytes) -> list[ParsedRow]`
and register its extensions below.
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from ..models import ParsedRow
from . import csv_parser, excel_parser, image_parser, json_parser, pdf_parser, txt_parser


class UnsupportedFormat(ValueError):
    pass


Parser = Callable[[bytes], list[ParsedRow]]

REGISTRY: dict[str, tuple[str, Parser]] = {
    ".csv": ("csv", csv_parser.parse),
    ".tsv": ("csv", csv_parser.parse),
    ".xlsx": ("excel", excel_parser.parse),
    ".xlsm": ("excel", excel_parser.parse),
    ".pdf": ("pdf", pdf_parser.parse),
    ".json": ("json", json_parser.parse),
    ".txt": ("text", txt_parser.parse),
    ".text": ("text", txt_parser.parse),
    ".log": ("text", txt_parser.parse),
    ".png": ("image", image_parser.parse),
    ".jpg": ("image", image_parser.parse),
    ".jpeg": ("image", image_parser.parse),
    ".webp": ("image", image_parser.parse),
}


def supported_extensions() -> list[str]:
    return sorted(REGISTRY)


def detect(filename: str, data: bytes) -> tuple[str, Parser]:
    if data[:5] == b"%PDF-":
        return REGISTRY[".pdf"]
    if data[:4] == b"PK\x03\x04" and Path(filename).suffix.lower() not in (".xlsx", ".xlsm"):
        return REGISTRY[".xlsx"]  # xlsx saved with a wrong/missing extension
    ext = Path(filename).suffix.lower()
    if ext in REGISTRY:
        return REGISTRY[ext]
    if ext == ".xls":
        raise UnsupportedFormat("Old .xls files aren't supported. Re-save as .xlsx or .csv.")
    # Unknown extension: if it decodes as text, try the text-capable CSV parser.
    try:
        data.decode("utf-8")
        return ("csv", csv_parser.parse)
    except UnicodeDecodeError:
        raise UnsupportedFormat(
            f"Unsupported file type '{ext or 'unknown'}'. "
            f"Supported: {', '.join(supported_extensions())}"
        ) from None


def parse_file(filename: str, data: bytes) -> tuple[str, list[ParsedRow]]:
    name, parser = detect(filename, data)
    return name, parser(data)
