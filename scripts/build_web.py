#!/usr/bin/env python3
"""Build the static web version of spendyFRD into dist/ (for GitHub Pages).

The Python backend runs in the browser via Pyodide, so no server is needed.

    python3 scripts/build_web.py            # -> dist/
    python3 -m http.server -d dist 8080     # preview at http://localhost:8080

Output:
    dist/index.html, *.css, *.js     frontend (config.js switched to browser mode)
    dist/locales/*.json              translations
    dist/py/spendy_app.zip           backend/app package (code, migrations, fonts)
    dist/py/wheels/*.whl             pinned pure-Python / wasm wheels (sha256-verified)
    dist/py/manifest.json            what the worker loads
Standard library only.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
CACHE = ROOT / ".cache" / "wheels"
REQS = ROOT / "scripts" / "web-requirements.txt"
WASM_TAG = "pyemscripten_2026_0_wasm32"
PYODIDE_PACKAGES = ["fastapi", "pydantic", "pillow", "fonttools", "cryptography",
                    "charset-normalizer", "micropip"]


def pins() -> list[tuple[str, str]]:
    out = []
    for line in REQS.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            name, version = line.split("==")
            out.append((name.strip(), version.strip()))
    return out


def fetch_wheel(name: str, version: str) -> Path:
    """Pick the pure-Python or Pyodide wheel from PyPI, verify its sha256, cache it."""
    with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json", timeout=30) as r:
        files = json.load(r)["urls"]
    wheels = [f for f in files if f["filename"].endswith(".whl")]
    choice = next((f for f in wheels if WASM_TAG in f["filename"]), None) or \
        next((f for f in wheels if f["filename"].endswith("-none-any.whl")), None)
    if not choice:
        sys.exit(f"No pure-Python or {WASM_TAG} wheel for {name}=={version}")
    target = CACHE / choice["filename"]
    expected = choice["digests"]["sha256"]
    if not (target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() == expected):
        CACHE.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(choice["url"], timeout=120) as r:
            data = r.read()
        if hashlib.sha256(data).hexdigest() != expected:
            sys.exit(f"sha256 mismatch for {choice['filename']}")
        target.write_bytes(data)
    return target


def build_id() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                                       text=True).strip()
    except Exception:
        return "dev"


def main() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    (DIST / "py" / "wheels").mkdir(parents=True)

    shutil.copytree(ROOT / "frontend", DIST, dirs_exist_ok=True)
    (DIST / "config.js").write_text('window.SPENDY_CONFIG = { mode: "browser" };\n')
    shutil.copytree(ROOT / "locales", DIST / "locales")
    (DIST / ".nojekyll").write_text("")  # serve files as-is on GitHub Pages

    app_dir = ROOT / "backend" / "app"
    with zipfile.ZipFile(DIST / "py" / "spendy_app.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(app_dir.rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts:
                z.write(f, f.relative_to(app_dir.parent).as_posix())

    wheels = []
    for name, version in pins():
        wheel = fetch_wheel(name, version)
        shutil.copy2(wheel, DIST / "py" / "wheels" / wheel.name)
        wheels.append(wheel.name)

    manifest = {"build": build_id(), "pyodide_packages": PYODIDE_PACKAGES, "wheels": wheels}
    (DIST / "py" / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    size = sum(f.stat().st_size for f in DIST.rglob("*") if f.is_file()) / 1e6
    print(f"Built {DIST.relative_to(ROOT)}/ ({size:.1f} MB, build {manifest['build']}, {len(wheels)} wheels)")


if __name__ == "__main__":
    main()
