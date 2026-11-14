"""SQLite connection + schema migrations.

Migrations are the numbered .sql files in ./migrations. The applied version is
stored in SQLite's built-in `PRAGMA user_version`, so each file runs exactly once.
To change the schema, add `0002_<name>.sql`; never edit a migration that has shipped.
"""
from __future__ import annotations

import os
import re
import sqlite3
import sys
from pathlib import Path

DEFAULT_DB = Path(__file__).resolve().parents[2] / "data" / "spendy.db"
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def db_path(path: str | Path | None = None) -> str:
    return str(path or os.environ.get("SPENDY_DB") or DEFAULT_DB)


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    target = db_path(path)
    if target != ":memory:":
        Path(target).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if target != ":memory:" and sys.platform != "emscripten":
        # WAL allows reads during writes; the browser build (Pyodide) has no shared memory for it
        conn.execute("PRAGMA journal_mode = WAL")
    migrate(conn)
    return conn


def migrations() -> list[tuple[int, Path]]:
    found = []
    for f in MIGRATIONS_DIR.glob("*.sql"):
        m = re.match(r"^(\d+)_", f.name)
        if m:
            found.append((int(m.group(1)), f))
    return sorted(found)


def migrate(conn: sqlite3.Connection) -> int:
    """Apply pending migrations in order; returns the resulting schema version."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for version, file in migrations():
        if version <= current:
            continue
        # one transaction per migration: either the whole file applies or none of it
        conn.executescript(f"BEGIN;\n{file.read_text(encoding='utf-8')}\nPRAGMA user_version = {version};\nCOMMIT;")
        current = version
    return current
