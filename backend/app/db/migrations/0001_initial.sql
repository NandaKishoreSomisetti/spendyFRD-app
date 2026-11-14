-- 0001: core schema
CREATE TABLE IF NOT EXISTS imports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filename    TEXT    NOT NULL,
    parser      TEXT,
    imported    INTEGER NOT NULL DEFAULT 0,
    duplicates  INTEGER NOT NULL DEFAULT 0,
    error       TEXT,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE TABLE IF NOT EXISTS transactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT,                                   -- ISO yyyy-mm-dd, NULL if unknown
    description TEXT    NOT NULL,
    amount      REAL    NOT NULL CHECK (amount > 0),
    type        TEXT    NOT NULL CHECK (type IN ('debit', 'credit')),
    category    TEXT    NOT NULL,
    source      TEXT    NOT NULL DEFAULT 'manual',      -- manual | csv | excel | pdf | json | text | image
    import_id   INTEGER REFERENCES imports(id) ON DELETE SET NULL,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
CREATE INDEX IF NOT EXISTS ix_tx_dedupe   ON transactions (date, amount, type, description);
CREATE INDEX IF NOT EXISTS ix_tx_category ON transactions (category);
CREATE INDEX IF NOT EXISTS ix_tx_import   ON transactions (import_id);

CREATE TRIGGER IF NOT EXISTS trg_tx_updated_at
AFTER UPDATE ON transactions FOR EACH ROW
WHEN NEW.updated_at = OLD.updated_at
BEGIN
    UPDATE transactions SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = NEW.id;
END;

-- merchant -> category, learned from user corrections
CREATE TABLE IF NOT EXISTS learned_rules (
    merchant_key TEXT PRIMARY KEY,
    category     TEXT NOT NULL,
    updated_at   TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
