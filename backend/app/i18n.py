"""Translations for server-generated output (the PDF report).

All strings live in the shared locale files at the repo root: locales/{en,te,hi}.json.
Each file has the sections "meta", "ui" (frontend), "categories" and "report" (this module).
Categories are stored in English in the database and translated only for display.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

LOCALES_DIR = Path(os.environ.get("SPENDY_LOCALES") or Path(__file__).resolve().parents[2] / "locales")
LANGS = ("en", "te", "hi")


@lru_cache(maxsize=None)
def load_locale(lang: str) -> dict:
    if lang not in LANGS:
        lang = "en"
    with open(LOCALES_DIR / f"{lang}.json", encoding="utf-8") as f:
        return json.load(f)


def category_label(category: str, lang: str) -> str:
    return load_locale(lang).get("categories", {}).get(category, category)


def report_text(lang: str, key: str, **kwargs: object) -> str:
    text = load_locale(lang).get("report", {}).get(key) or load_locale("en")["report"][key]
    return text.format(**kwargs)
