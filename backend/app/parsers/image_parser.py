"""Images (screenshots / photos of statements) via OCR. Optional dependency."""
from __future__ import annotations

import io

from ..models import ParsedRow
from .text_parser import parse_text


class OCRUnavailable(RuntimeError):
    pass


def parse(data: bytes) -> list[ParsedRow]:
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:
        raise OCRUnavailable(
            "Image upload needs OCR: pip install pytesseract pillow, and install tesseract "
            "(macOS: brew install tesseract)."
        ) from exc
    try:
        text = pytesseract.image_to_string(Image.open(io.BytesIO(data)))
    except pytesseract.TesseractNotFoundError as exc:
        raise OCRUnavailable("Tesseract is not installed (macOS: brew install tesseract).") from exc
    return parse_text(text)
