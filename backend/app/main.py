"""Entry point: `uvicorn app.main:app --reload` from the backend/ folder.

Serves the API under /api, docs at /docs, translations at /locales, and the frontend at /.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api import router

ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DIR = ROOT / "frontend"
LOCALES_DIR = ROOT / "locales"

app = FastAPI(title="spendyFRD API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5500", "http://127.0.0.1:5500"],  # e.g. VS Code Live Server
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)

if LOCALES_DIR.is_dir():  # shared translation files, used by the frontend
    app.mount("/locales", StaticFiles(directory=LOCALES_DIR), name="locales")
if FRONTEND_DIR.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
