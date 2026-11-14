# Hosting on GitHub Pages

GitHub Pages only serves static files, so the web version runs the **same Python backend
inside the browser** with [Pyodide](https://pyodide.org) (Python compiled to WebAssembly).
No server is involved, and statements and transactions never leave the user's device.

```
browser ── index.html / app.js ── fetch-like calls ──► py-worker.js (Web Worker)
                                                          └─ Pyodide 314.0.7
                                                              └─ backend/app (FastAPI app, parsers,
                                                                 categoriser, SQLite, PDF report)
                                                                 DB: /data/spendy.db on IndexedDB
```

| | Server mode (`./run.sh`) | Web mode (GitHub Pages) |
|---|---|---|
| Python runs | on your machine (uvicorn) | in the browser tab (Pyodide) |
| Database | `backend/data/spendy.db` | IndexedDB in that browser |
| First load | instant | about 25 MB once, then cached |
| Image (OCR) upload | yes, with tesseract installed | no |
| Everything else | same code | same code |

`frontend/config.js` selects the mode. The build switches it to `"browser"`.

## Build and preview locally

```bash
python3 scripts/build_web.py              # creates dist/ (wheels are sha256-verified from PyPI)
python3 -m http.server -d dist 8080       # http://localhost:8080
```

## Deploy

`.github/workflows/deploy-web.yml` runs the tests, builds `dist/` and publishes it on every push to
`main` (or run it manually from the Actions tab). One-time setup in the repo:
**Settings → Pages → Build and deployment → Source: GitHub Actions**.

## Updating the browser packages

- Pyodide version: `PYODIDE_VERSION` in `frontend/py-worker.js`.
- Extra wheels: `scripts/web-requirements.txt` (pure-Python, or a `pyemscripten_2026_0` wheel matching Pyodide's ABI).
- Packages Pyodide already includes: `PYODIDE_PACKAGES` in `scripts/build_web.py`.
- Browser-only workarounds (no threads, no native `pypdfium2`): `backend/app/wasm.py`.
