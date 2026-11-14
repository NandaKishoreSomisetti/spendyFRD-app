"""Helpers that turn messy statement strings into clean values."""
from __future__ import annotations

import re
from datetime import date, datetime

_DATE_FORMATS = (
    "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y",
    "%Y-%m-%d", "%Y/%m/%d",
    "%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%d-%b-%y", "%d %b %y",
    "%b %d, %Y", "%B %d, %Y", "%b %d %Y",
)

# Matches the date shapes above inside free text.
DATE_RE = re.compile(
    r"\b(\d{4}[/-]\d{1,2}[/-]\d{1,2}"
    r"|\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}"
    r"|\d{1,2}[ -](?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?[ -]\d{2,4}"
    r"|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.? \d{1,2},? \d{4})\b",
    re.IGNORECASE,
)

_CURRENCY_RE = re.compile(r"(₹|rs\.?|inr|\$|usd)", re.IGNORECASE)


def parse_date(value: object) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    text = re.sub(r"[T ]\d{1,2}:\d{2}(:\d{2})?.*$", "", text)  # drop time part
    text = text.replace("Sept", "Sep").replace("sept", "sep")
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def parse_amount(value: object) -> float | None:
    """'₹1,250.00' -> 1250.0, '(500)' -> -500.0, '500 Dr' -> 500.0. None if not a number."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text or text in {"-", "--", "—"}:
        return None
    negative = (text.startswith("(") and text.endswith(")")) or text.startswith("-")
    text = _CURRENCY_RE.sub("", text)
    text = re.sub(r"\b(dr|cr)\b\.?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[,\s()+-]", "", text)
    if not re.fullmatch(r"\d+(\.\d+)?", text):
        return None
    amount = float(text)
    return -amount if negative else amount


_CREDIT_WORDS = re.compile(
    r"\b(cr|credit|credited|received|deposit|deposited|refund|salary|cashback|"
    r"interest|pocket money|prize|reversal)\b",
    re.IGNORECASE,
)
_DEBIT_WORDS = re.compile(
    r"\b(dr|debit|debited|paid|sent|withdrawal|withdrawn|purchase|spent|pos)\b",
    re.IGNORECASE,
)


def guess_is_credit(text: str) -> bool:
    """Heuristic for free text: credit words present and no debit words."""
    return bool(_CREDIT_WORDS.search(text)) and not _DEBIT_WORDS.search(text)


def clean_description(text: str) -> str:
    text = re.sub(r"\s+", " ", str(text)).strip(" -|:;,")
    return text[:200] or "Transaction"
