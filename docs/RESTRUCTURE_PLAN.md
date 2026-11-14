# spendyFRD — Restructure Plan

The new app is built **from scratch** next to the previous version, which stays untouched on `main`
(the root `index.html`, `dashboard.*`, `auth.*`, `app.js` and `i18n.js` files, plus the live GitHub Pages site).

## Branches

```
main ─────────────────────────────── previous version (unchanged)
  └─ feature/spendy_frd_db           SQLite schema, migrations, repository
       └─ feature/spendy_frd_backend  parsers, categoriser, REST API, PDF report, locales/
            └─ feature/spendy_frd_frontend  single-page UI, run.sh, docs
```

Each branch builds on the one before it, so `feature/spendy_frd_frontend` contains the complete
new app. Every branch's own tests pass on that branch.

## Run

```bash
./run.sh            # first run creates backend/.venv and installs dependencies
# open http://localhost:8000      API docs: http://localhost:8000/docs
cd backend && .venv/bin/python -m pytest     # tests
```

## 1. Goal

Upload **any** statement file → the app reads it → every transaction is
auto-categorised. Users can also **add entries manually**. The UI is simple,
clean and clear.

## 2. Problems with the current version

| Area | Issue |
|---|---|
| Architecture | All logic lives in one ~1,800-line `app.js` (parsing, charts, PDF export, UI). Hard to test or extend. |
| File formats | Only PDF / CSV / TXT, all pushed through one regex-based line parser. No Excel, JSON, or column-aware parsing. |
| Parsing | CSV columns are ignored. Amounts are guessed from "last number on the line", so balances and IDs get picked up as amounts. |
| Categorisation | Substring matching with no word boundaries: `"vi"` matches "ser**vi**ce", `"tea"` matches "s**tea**m", `"fee"` matches "cof**fee**". The app never learns from user corrections. |
| Auth | "Login" is fake (`localStorage` only), which adds screens without adding security. |
| UI | Two pages, glass effects, many panels. Too much for the core job. |

## 3. Target architecture

```
spendyFRD/
├── backend/                      # Python API (FastAPI)
│   ├── app/
│   │   ├── main.py               # FastAPI app; also serves frontend/
│   │   ├── api.py                # REST routes
│   │   ├── models.py             # Pydantic schemas
│   │   ├── db/                   # SQLite: connection.py, repository.py, migrations/*.sql
│   │   ├── report.py             # PDF report (fpdf2 + Noto fonts)
│   │   ├── i18n.py               # reads locales/*.json for the report
│   │   ├── categorizer.py        # keyword rules + learned rules
│   │   ├── normalize.py          # dates, amounts, debit/credit helpers
│   │   └── parsers/
│   │       ├── __init__.py       # registry: extension → parser
│   │       ├── tabular.py        # header detection + column mapping (shared)
│   │       ├── text_parser.py    # free-text / line-based fallback
│   │       ├── csv_parser.py     # .csv .tsv
│   │       ├── excel_parser.py   # .xlsx .xlsm
│   │       ├── pdf_parser.py     # .pdf (tables first, text fallback)
│   │       ├── json_parser.py    # .json
│   │       └── image_parser.py   # .png .jpg (OCR, optional)
│   ├── tests/
│   └── requirements.txt
├── frontend/                     # Plain HTML + CSS + JS (no build step)
│   ├── index.html
│   ├── styles.css
│   ├── i18n.js
│   └── app.js
├── locales/                      # en.json, te.json, hi.json (see docs/TRANSLATIONS.md)
├── run.sh
└── docs/
```

### Why FastAPI + plain HTML/JS?

- **FastAPI**: async file uploads, automatic validation, and free interactive
  docs at `/docs`. It is the standard choice for a small Python API.
- **Keep the frontend as plain HTML/CSS/JS** (the current format). The UI is
  one screen, so React or a build step would add weight with no benefit. The
  API serves the frontend directly, so it runs with a single command.
- **SQLite**: built into Python, a single file, no server to run.
- *Alternative considered:* Streamlit, which would be pure Python. It is quick,
  but you get far less control over a "clean and simple" design, so I don't
  recommend it here.

## 4. Processing pipeline

```
upload ─► detect format (extension + magic bytes)
       ─► parser → raw rows
       ─► tabular: find header row, map columns
             (date / description / debit / credit / amount / type)
          or text fallback: line-based date + amount extraction
       ─► normalize (date formats, ₹/INR/commas, (500), "Dr/Cr")
       ─► categorize (learned rules → keyword rules → "Other"; credits → "Income")
       ─► de-duplicate (date + description + amount + type)
       ─► save to SQLite ─► return the imported rows
```

The categoriser **learns**: when a user changes a transaction's category, the
merchant key is saved, and future imports from that merchant use the new
category.

## 5. API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | liveness |
| GET | `/api/formats` | supported file types |
| GET | `/api/categories` | category list |
| POST | `/api/upload` | upload 1..n files → parse + categorise + save |
| GET | `/api/transactions` | list (filters: `category`, `type`, `q`) |
| POST | `/api/transactions` | manual entry (category auto-filled if blank) |
| PATCH | `/api/transactions/{id}` | edit (category change teaches the categoriser) |
| DELETE | `/api/transactions/{id}` | delete one |
| DELETE | `/api/transactions` | clear all |
| GET | `/api/summary` | totals, net, per-category breakdown |
| GET | `/api/export.csv` | CSV download |
| GET | `/api/report.pdf?lang=en\|te\|hi` | PDF report in the chosen language |
| GET | `/api/imports` | upload history |
| GET | `/locales/{lang}.json` | translation files |

## Database (`backend/app/db/`)

- SQLite file at `backend/data/spendy.db` (override with `SPENDY_DB`). It is git-ignored, so each install has its own data.
- Tables: `transactions`, `imports` (upload history; transactions link to it, `ON DELETE SET NULL`),
  and `learned_rules` (merchant → category).
- CHECK constraints on amount and type, indexes for de-duplication and filters, and an `updated_at` trigger.
- Migrations are numbered files in `migrations/`, tracked with `PRAGMA user_version`.
  To change the schema, add `0002_<name>.sql`; never edit a migration that has already been released.
- Foreign keys are enforced, and the WAL journal allows reads while a write is in progress.

## 6. UI (single page)

```
┌─────────────────────────────────────────────────────┐
│ spendyFRD                                  [☀/☾]    │
├─────────────────────────────────────────────────────┤
│  ┌───────────── Drop any file here ──────────────┐  │
│  │  PDF · CSV · Excel · JSON · TXT · Image       │  │
│  └───────────────────────────────────────────────┘  │
│  [ + Add entry ]                                    │
├─────────────────────────────────────────────────────┤
│  Income ₹…     Spent ₹…     Balance ₹…              │
│  Category bars (click to filter)                    │
├─────────────────────────────────────────────────────┤
│  Search…   [All|Spent|Income]          [Export CSV] │
│  Date  Description        Category ▾   Amount  ✕    │
└─────────────────────────────────────────────────────┘
```

- One screen, no login, a single accent colour, light and dark themes.
- Change the category inline from a dropdown (this teaches the categoriser).

## 7. Phases

1. **Backend core**: parsers, normaliser, categoriser, storage, API, tests. *(done)*
2. **Frontend rewrite**: the single page above, wired to the API, responsive on phone, tablet and desktop. *(done)*
3. **Run script and docs.** *(done.)* The previous version is deliberately kept as it is.
4. **Optional extras**: OCR for images and scanned PDFs, and hosting (see below).

## 8. Decisions made

- Login removed. Telugu and Hindi kept, and the PDF report download kept (also translated).

## 9. Hosting

GitHub Pages only serves static files, so it cannot run the Python API. The options are covered in the hand-over notes.
