import sqlite3
from datetime import date

from app.db import Store, connect
from app.db.connection import migrations
from app.models import TxType


def test_migrations_set_version_and_are_idempotent(tmp_path):
    path = tmp_path / "t.db"
    latest = migrations()[-1][0]
    conn = connect(path)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == latest
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    conn.close()
    conn = connect(path)  # reopening must not re-run or fail
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"transactions", "learned_rules", "imports"} <= tables
    conn.close()


def test_crud_and_filters(store):
    a = store.add(date(2026, 11, 1), "Swiggy", 300, TxType.DEBIT, "Food & Dining", "csv")
    store.add(None, "Pocket money", 5000, TxType.CREDIT, "Income", "manual")
    assert store.get(a.id).description == "Swiggy"
    assert len(store.list(tx_type=TxType.CREDIT)) == 1
    assert len(store.list(q="swig")) == 1
    assert store.list(q="100%") == []  # LIKE wildcards are escaped
    # dated rows first, newest first; undated last
    assert [t.description for t in store.list()] == ["Swiggy", "Pocket money"]
    store.update(a.id, {"category": "Groceries", "id": 999})  # unknown keys ignored
    assert store.get(a.id).category == "Groceries"
    assert store.exists(date(2026, 11, 1), "Swiggy", 300, TxType.DEBIT)
    assert store.delete(a.id) and not store.delete(a.id)
    assert store.clear() == 1


def test_amount_must_be_positive(store):
    try:
        store.add(None, "x", 0, TxType.DEBIT, "Other", "manual")
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("CHECK constraint not enforced")


def test_updated_at_trigger(store):
    tx = store.add(None, "x", 1, TxType.DEBIT, "Other", "manual")
    before = store._conn.execute("SELECT updated_at FROM transactions WHERE id=?", (tx.id,)).fetchone()[0]
    store._conn.execute("UPDATE transactions SET updated_at='2000-01-01' WHERE id=?", (tx.id,))
    store.update(tx.id, {"category": "Health"})
    after = store._conn.execute("SELECT updated_at FROM transactions WHERE id=?", (tx.id,)).fetchone()[0]
    assert after > "2000-01-01" and before


def test_imports_and_fk(store):
    imp = store.start_import("s.csv", "csv")
    tx = store.add(None, "x", 1, TxType.DEBIT, "Other", "csv", import_id=imp)
    store.finish_import(imp, 1, 0)
    assert store.imports()[0].imported == 1
    store._conn.execute("DELETE FROM imports")
    row = store._conn.execute("SELECT import_id FROM transactions WHERE id=?", (tx.id,)).fetchone()
    assert row[0] is None  # ON DELETE SET NULL


def test_learned_rules_upsert(store):
    store.learn("ramesh stores", "Groceries")
    store.learn("ramesh stores", "Shopping")
    store.learn("", "Other")
    assert store.learned_rules() == {"ramesh stores": "Shopping"}
