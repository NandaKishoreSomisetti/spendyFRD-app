"""Repository: every SQL query the app runs lives here."""
from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterable
from datetime import date
from pathlib import Path

from ..models import ImportRecord, Transaction, TxType
from .connection import connect

_TX_COLUMNS = "id, date, description, amount, type, category, source"


def _row_to_tx(row: sqlite3.Row) -> Transaction:
    return Transaction(
        id=row["id"],
        date=date.fromisoformat(row["date"]) if row["date"] else None,
        description=row["description"],
        amount=row["amount"],
        type=TxType(row["type"]),
        category=row["category"],
        source=row["source"],
    )


def _sql_value(value: object) -> object:
    if isinstance(value, TxType):
        return value.value
    if isinstance(value, date):
        return value.isoformat()
    return value


class Store:
    """Thread-safe access to the SQLite database (one connection, writes serialised)."""

    def __init__(self, path: str | Path | None = None):
        self._conn = connect(path)
        self._lock = threading.Lock()

    def close(self) -> None:
        self._conn.close()

    # ---- transactions -------------------------------------------------------
    def exists(self, d: date | None, description: str, amount: float, tx_type: TxType) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM transactions WHERE date IS ? AND description = ? "
            "AND amount = ? AND type = ? LIMIT 1",
            (_sql_value(d), description, amount, tx_type.value),
        ).fetchone()
        return row is not None

    def add(self, d: date | None, description: str, amount: float, tx_type: TxType,
            category: str, source: str, import_id: int | None = None) -> Transaction:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO transactions (date, description, amount, type, category, source, import_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (_sql_value(d), description, amount, tx_type.value, category, source, import_id),
            )
        return self.get(cur.lastrowid)  # type: ignore[return-value, arg-type]

    def get(self, tx_id: int) -> Transaction | None:
        row = self._conn.execute(
            f"SELECT {_TX_COLUMNS} FROM transactions WHERE id = ?", (tx_id,)
        ).fetchone()
        return _row_to_tx(row) if row else None

    def list(self, category: str | None = None, tx_type: TxType | None = None,
             q: str | None = None) -> list[Transaction]:
        sql = f"SELECT {_TX_COLUMNS} FROM transactions WHERE 1=1"
        params: list[object] = []
        if category:
            sql += " AND category = ?"
            params.append(category)
        if tx_type:
            sql += " AND type = ?"
            params.append(tx_type.value)
        if q:
            sql += " AND (description LIKE ? ESCAPE '\\' OR category LIKE ? ESCAPE '\\')"
            like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            params += [like, like]
        sql += " ORDER BY date IS NULL, date DESC, id DESC"
        return [_row_to_tx(r) for r in self._conn.execute(sql, params)]

    def update(self, tx_id: int, fields: dict[str, object]) -> Transaction | None:
        allowed = ("date", "description", "amount", "type", "category")
        fields = {k: v for k, v in fields.items() if k in allowed}
        if fields:
            assignments = ", ".join(f"{k} = ?" for k in fields)  # keys are whitelisted above
            with self._lock, self._conn:
                self._conn.execute(
                    f"UPDATE transactions SET {assignments} WHERE id = ?",
                    (*map(_sql_value, fields.values()), tx_id),
                )
        return self.get(tx_id)

    def delete(self, tx_id: int) -> bool:
        with self._lock, self._conn:
            cur = self._conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
        return cur.rowcount > 0

    def clear(self) -> int:
        with self._lock, self._conn:
            cur = self._conn.execute("DELETE FROM transactions")
            self._conn.execute("DELETE FROM imports")
        return cur.rowcount

    def recategorize(self, ids: Iterable[int], category: str) -> None:
        ids = list(ids)
        if not ids:
            return
        with self._lock, self._conn:
            self._conn.execute(
                f"UPDATE transactions SET category = ? WHERE id IN ({','.join('?' * len(ids))})",
                (category, *ids),
            )

    # ---- imports (upload history) --------------------------------------------
    def start_import(self, filename: str, parser: str | None) -> int:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO imports (filename, parser) VALUES (?, ?)", (filename, parser)
            )
        return cur.lastrowid  # type: ignore[return-value]

    def finish_import(self, import_id: int, imported: int, duplicates: int,
                      error: str | None = None) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE imports SET imported = ?, duplicates = ?, error = ? WHERE id = ?",
                (imported, duplicates, error, import_id),
            )

    def imports(self, limit: int = 50) -> list[ImportRecord]:
        rows = self._conn.execute(
            "SELECT id, filename, parser, imported, duplicates, error, created_at "
            "FROM imports ORDER BY id DESC LIMIT ?", (limit,),
        )
        return [ImportRecord(**dict(r)) for r in rows]

    # ---- learned rules ------------------------------------------------------
    def learned_rules(self) -> dict[str, str]:
        return {
            r["merchant_key"]: r["category"]
            for r in self._conn.execute("SELECT merchant_key, category FROM learned_rules")
        }

    def learn(self, key: str, category: str) -> None:
        if not key:
            return
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO learned_rules (merchant_key, category) VALUES (?, ?) "
                "ON CONFLICT(merchant_key) DO UPDATE SET category = excluded.category, "
                "updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')",
                (key, category),
            )
