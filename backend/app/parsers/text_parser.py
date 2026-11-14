"""Line-based fallback for statements without a detectable table (PDF text, TXT, OCR)."""
from __future__ import annotations

import re

from ..models import ParsedRow, TxType
from ..normalize import DATE_RE, clean_description, guess_is_credit, parse_amount, parse_date

_SKIP = re.compile(
    r"^(date|txn|particulars|description|narration|opening balance|closing balance|total|"
    r"statement|page \d+|transaction id|utr|account|customer|branch|ifsc)\b",
    re.IGNORECASE,
)
_TIME = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:am|pm)?\b", re.IGNORECASE)
_LONG_ID = re.compile(r"\b[A-Z0-9]*\d{7,}[A-Z0-9]*\b", re.IGNORECASE)
_MONEY = re.compile(
    r"(?:₹|rs\.?|inr)\s*\d[\d,]*(?:\.\d{1,2})?(?:\s*(?:cr|dr)\b)?"
    r"|\b\d{1,3}(?:,\d{2,3})+(?:\.\d{1,2})?(?:\s*(?:cr|dr)\b)?"
    r"|\b\d+\.\d{2}\b(?:\s*(?:cr|dr)\b)?",
    re.IGNORECASE,
)
_HAS_CURRENCY = re.compile(r"₹|rs\.?\s*\d|inr\s*\d", re.IGNORECASE)


def parse_text(text: str) -> list[ParsedRow]:
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    rows: list[ParsedRow] = []
    last_date = None

    for i, line in enumerate(lines):
        if _SKIP.match(line):
            continue

        date_match = DATE_RE.search(line)
        if date_match:
            parsed = parse_date(date_match.group(0))
            if parsed:
                last_date = parsed

        stripped = DATE_RE.sub(" ", line)
        stripped = _TIME.sub(" ", stripped)
        stripped = _LONG_ID.sub(" ", stripped)
        money = _MONEY.findall(stripped)
        if not money:
            continue

        # Bank rows often end with "amount  balance"; UPI apps show one ₹ amount.
        has_currency = bool(_HAS_CURRENCY.search(stripped))
        token = money[-2] if (len(money) >= 2 and not has_currency) else money[-1]
        amount = parse_amount(token)
        if not amount or abs(amount) > 10_000_000:
            continue

        description = _MONEY.sub(" ", stripped)
        description = re.sub(r"\b(debit|credit|dr|cr)\b\.?", " ", description, flags=re.I)
        description = clean_description(description)
        if len(re.sub(r"[^a-z]", "", description.lower())) < 2:
            # amount-only line (common in PhonePe/GPay exports): borrow the previous line
            prev = lines[i - 1] if i > 0 else ""
            description = clean_description(_MONEY.sub(" ", DATE_RE.sub(" ", prev)))

        context = " ".join(lines[max(0, i - 1): i + 2])
        if re.search(r"\bcr\b", token, re.I):
            tx_type = TxType.CREDIT
        elif re.search(r"\bdr\b", token, re.I) or amount < 0:
            tx_type = TxType.DEBIT
        elif guess_is_credit(line) or (guess_is_credit(context) and not re.search(r"\b(dr|debit|paid)\b", line, re.I)):
            tx_type = TxType.CREDIT
        else:
            tx_type = TxType.DEBIT

        rows.append(ParsedRow(description, round(abs(amount), 2), tx_type, last_date))
    return rows
