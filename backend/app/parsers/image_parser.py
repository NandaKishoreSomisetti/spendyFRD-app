"""Images (screenshots / photos of statements) via OCR. Optional dependency."""
from __future__ import annotations

import io
import sys

from ..models import ParsedRow
from .text_parser import parse_text


class OCRUnavailable(RuntimeError):
    pass


def parse(data: bytes) -> list[ParsedRow]:
    if sys.platform == "emscripten":
        raise OCRUnavailable("Image upload (OCR) isn't available in the web version. "
                             "Upload a PDF, CSV or Excel file instead.")
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
