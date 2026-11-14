#!/usr/bin/env bash
# Start spendyFRD: creates the Python env on first run, then serves API + UI.
# Usage: ./run.sh [port]      (default 8000) → open http://localhost:<port>
set -euo pipefail
cd "$(dirname "$0")/backend"
PORT="${1:-8000}"
if [ ! -x .venv/bin/python ]; then
  echo "Setting up Python environment (first run)…"
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
fi
echo "spendyFRD running at http://localhost:${PORT}  (API docs: /docs, stop: Ctrl+C)"
exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$PORT"
