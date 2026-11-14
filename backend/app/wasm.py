"""Run the FastAPI app inside the browser with Pyodide (no server).

The web build (GitHub Pages) loads this package into a Web Worker. frontend/py-worker.js
forwards every `/api/...` request to `handle()`, which calls the same ASGI app the
server uses, so routing, validation, parsing, categorising and the PDF report all
come from the same code.

Pyodide differences handled here:
- No threads: FastAPI/Starlette run sync endpoints in a threadpool, so they are run inline.
- pdfplumber imports pypdfium2 (native) only to render page images, which we never do,
  so a placeholder module is registered and table extraction still works.
"""
from __future__ import annotations

import sys
import types


def _install_shims() -> None:
    if sys.platform != "emscripten":  # normal CPython: nothing to patch
        return
    if "pypdfium2" not in sys.modules:
        stub = types.ModuleType("pypdfium2")

        class PdfiumError(Exception):
            pass

        stub.PdfiumError = PdfiumError  # type: ignore[attr-defined]
        sys.modules["pypdfium2"] = stub

    async def run_inline(func, *args, **kwargs):
        return func(*args, **kwargs)

    import fastapi.concurrency
    import fastapi.dependencies.utils
    import fastapi.routing
    import starlette.concurrency
    import starlette.datastructures

    for module in (starlette.concurrency, starlette.datastructures, fastapi.concurrency,
                   fastapi.routing, fastapi.dependencies.utils):
        if hasattr(module, "run_in_threadpool"):
            module.run_in_threadpool = run_inline  # type: ignore[attr-defined]


_install_shims()

from .main import app  # noqa: E402  (shims must be installed first)


async def handle(method: str, path: str, query: str, headers: list[list[str]],
                 body: bytes) -> tuple[int, list[list[str]], bytes]:
    """Dispatch one HTTP request to the ASGI app and collect the response."""
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method.upper(),
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": query.encode(),
        "root_path": "",
        "headers": [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in headers],
        "client": ("127.0.0.1", 0),
        "server": ("localhost", 80),
    }
    request_sent = False

    async def receive() -> dict:
        nonlocal request_sent
        if not request_sent:
            request_sent = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}
        return {"type": "http.disconnect"}

    status = 500
    response_headers: list[list[str]] = []
    chunks: list[bytes] = []

    async def send(message: dict) -> None:
        nonlocal status, response_headers
        if message["type"] == "http.response.start":
            status = message["status"]
            response_headers = [[k.decode("latin-1"), v.decode("latin-1")]
                                for k, v in message.get("headers", [])]
        elif message["type"] == "http.response.body":
            chunks.append(message.get("body", b""))

    await app(scope, receive, send)
    return status, response_headers, b"".join(chunks)
