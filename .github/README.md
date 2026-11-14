# spendyFRD: your money, sorted

**Live app:** https://nandakishoresomisetti.github.io/spendyFRD-app/

Upload a bank or UPI statement in almost any format and every transaction is read and
sorted into a category automatically. You can also add entries by hand. Available in
English, తెలుగు and हिन्दी, with a downloadable PDF report.

- **Any file:** PDF, CSV/TSV, Excel (.xlsx), JSON and TXT from any bank or UPI app. Image upload (OCR) works only in server mode.
- **Auto-categorised:** whole-word merchant rules, and it learns when you correct a category.
- **Private:** on the website, the Python backend runs *inside your browser*
  ([Pyodide](https://pyodide.org)), so your statements never leave your device.
- **Simple UI:** one page with an upload area, totals, category breakdown and transactions. Light and dark themes, works on phone and desktop.

## Run it

| | How | Where the Python runs |
|---|---|---|
| Website | open the live link above | in the browser (data stored in IndexedDB) |
| Local server | `./run.sh` → http://localhost:8000 | FastAPI on your machine (SQLite in `backend/data/`) |
| Local web build | `python3 scripts/build_web.py && python3 -m http.server -d dist 8080` | in the browser |

Tests: `cd backend && .venv/bin/python -m pytest` (created by `./run.sh`).

## Project layout

```
backend/app/      FastAPI app: parsers/, categorizer.py, db/ (SQLite + migrations), report.py (PDF), wasm.py (browser bridge)
frontend/         index.html, styles.css, app.js, i18n.js, py-worker.js (Pyodide worker), config.js
locales/          en.json, te.json, hi.json: all UI, category and report text
scripts/          build_web.py: builds dist/ for GitHub Pages
.github/workflows deploy-web.yml: test → build → deploy on every push to main
```

## Docs

- [Architecture and plan](../docs/RESTRUCTURE_PLAN.md)
- [Hosting and the browser build](../docs/HOSTING.md)
- [Translations (JSON format)](../docs/TRANSLATIONS.md)

## Branches

`feature/spendy_frd_db` → `feature/spendy_frd_backend` → `feature/spendy_frd_frontend` (each builds on the previous one).
`main` is the deployed app.

The files at the repo root (`index.html`, `dashboard.*`, `auth.*`, `app.js`, `i18n.js`, `README.md`) are the
previous browser-only version, kept unchanged for reference. The live app above is built from
`backend/`, `frontend/` and `locales/`.
