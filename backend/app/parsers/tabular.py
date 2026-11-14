"""Turn a grid of cells (CSV rows, Excel sheet, PDF table, JSON records) into ParsedRows.

Finds the header row, maps columns by name, then reads each data row.
Returns None when no usable header is found so callers can fall back to text parsing.
"""
from __future__ import annotations

import re
from collections.abc import Sequence

from ..models import ParsedRow, TxType
from ..normalize import clean_description, guess_is_credit, parse_amount, parse_date

Grid = Sequence[Sequence[object]]

ALIASES: dict[str, tuple[str, ...]] = {
    "date": ("date", "txn date", "transaction date", "value date", "posting date",
             "tran date", "trans date", "date time", "datetime", "booking date"),
    "description": ("description", "narration", "particulars", "details", "remarks",
                    "transaction details", "merchant", "name", "payee", "memo",
                    "transaction remarks", "transaction description", "note", "notes"),
    "debit": ("debit", "debits", "withdrawal", "withdrawals", "withdrawal amt",
              "withdrawal amount", "debit amount", "dr amount", "paid out", "money out",
              "dr", "spent", "expense"),
    "credit": ("credit", "credits", "deposit", "deposits", "deposit amt", "deposit amount",
               "credit amount", "cr amount", "paid in", "money in", "cr", "received", "income"),
    "amount": ("amount", "amt", "transaction amount", "txn amount", "value", "amount inr",
               "amount rs", "inr", "rs"),
    "type": ("type", "dr cr", "cr dr", "dr/cr", "cr/dr", "transaction type", "txn type",
             "debit credit", "debit/credit"),
    "category": ("category", "categories"),
}

_MAX_HEADER_SCAN = 25


def _norm(cell: object) -> str:
    text = str(cell or "").lower().strip()
    text = re.sub(r"\(.*?\)", "", text)  # "Amount (INR)" -> "amount"
    text = re.sub(r"[^a-z/ ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _match_field(cell: object) -> str | None:
    name = _norm(cell)
    if not name:
        return None
    for field, aliases in ALIASES.items():
        if name in aliases:
            return field
    # looser: "withdrawal amount inr" startswith "withdrawal"
    for field, aliases in ALIASES.items():
        if any(len(a) > 3 and name.startswith(a) for a in aliases):
            return field
    return None


def _find_header(grid: Grid) -> tuple[int, dict[str, int]] | None:
    for row_idx, row in enumerate(grid[:_MAX_HEADER_SCAN]):
        mapping: dict[str, int] = {}
        for col_idx, cell in enumerate(row):
            field = _match_field(cell)
            if field and field not in mapping:
                mapping[field] = col_idx
        has_money = "amount" in mapping or "debit" in mapping or "credit" in mapping
        if has_money and ("description" in mapping or "date" in mapping):
            return row_idx, mapping
    return None


def _cell(row: Sequence[object], idx: int | None) -> object:
    if idx is None or idx >= len(row):
        return None
    value = row[idx]
    return value.strip() if isinstance(value, str) else value


def parse_grid(grid: Grid) -> list[ParsedRow] | None:
    found = _find_header(grid)
    if not found:
        return None
    header_idx, cols = found
    rows: list[ParsedRow] = []

    for raw in grid[header_idx + 1:]:
        if not raw or all(c in (None, "") for c in raw):
            continue

        desc_val = _cell(raw, cols.get("description"))
        if desc_val in (None, ""):
            # no description column: use the non-numeric cells joined
            desc_val = " ".join(
                str(c) for i, c in enumerate(raw)
                if i not in cols.values() and c not in (None, "") and parse_amount(c) is None
            )
        description = clean_description(desc_val or "")
        if re.match(r"^(opening|closing) balance|^total\b|^balance b/?f", description, re.I):
            continue

        debit = parse_amount(_cell(raw, cols.get("debit")))
        credit = parse_amount(_cell(raw, cols.get("credit")))
        amount = parse_amount(_cell(raw, cols.get("amount")))
        type_cell = str(_cell(raw, cols.get("type")) or "").strip().lower()

        if debit and abs(debit) > 0:
            value, tx_type = abs(debit), TxType.DEBIT
        elif credit and abs(credit) > 0:
            value, tx_type = abs(credit), TxType.CREDIT
        elif amount:
            value = abs(amount)
            if type_cell.startswith(("cr", "credit", "in", "deposit", "received")):
                tx_type = TxType.CREDIT
            elif type_cell.startswith(("dr", "debit", "out", "withdraw", "paid", "sent")):
                tx_type = TxType.DEBIT
            elif amount < 0:
                tx_type = TxType.DEBIT
            elif "amount" in cols and isinstance(raw[cols["amount"]], str) and re.search(
                r"\bcr\b", str(raw[cols["amount"]]), re.I
            ):
                tx_type = TxType.CREDIT
            else:
                tx_type = TxType.CREDIT if guess_is_credit(description) else TxType.DEBIT
        else:
            continue

        rows.append(
            ParsedRow(
                description=description,
                amount=round(value, 2),
                type=tx_type,
                date=parse_date(_cell(raw, cols.get("date"))),
                category_hint=(str(_cell(raw, cols.get("category")) or "") or None),
            )
        )
    return rows
