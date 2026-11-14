"""The browser bridge (app.wasm.handle) must behave like the HTTP server.

Pyodide itself is exercised by the web build smoke test; here the same
dispatch code runs on CPython.
"""
import asyncio
import json

import pytest

from app import api
from app.main import app
from app.wasm import handle


@pytest.fixture()
def bridge(store):
    app.dependency_overrides[api.get_store] = lambda: store
    yield lambda *a: asyncio.run(handle(*a))
    app.dependency_overrides.clear()


def test_get_and_json_post(bridge):
    status, _, body = bridge("GET", "/api/health", "", [], b"")
    assert status == 200 and json.loads(body) == {"status": "ok"}
    status, _, body = bridge("POST", "/api/transactions", "", [["content-type", "application/json"]],
                             json.dumps({"description": "Rapido", "amount": 50}).encode())
    assert status == 201 and json.loads(body)["category"] == "Travel & Transport"
    status, _, _ = bridge("POST", "/api/transactions", "", [["content-type", "application/json"]],
                          b'{"description": "x", "amount": -1}')
    assert status == 422


def test_multipart_upload_and_binary_response(bridge):
    boundary = "XyZ"
    payload = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"s.csv\"\r\n"
        "Content-Type: text/csv\r\n\r\n"
        "Date,Description,Amount\r\n2026-11-01,Swiggy,-250\r\n"
        f"\r\n--{boundary}--\r\n"
    ).encode()
    status, _, body = bridge("POST", "/api/upload", "",
                             [["content-type", f"multipart/form-data; boundary={boundary}"]], payload)
    assert status == 200 and json.loads(body)["files"][0]["imported"] == 1
    status, headers, body = bridge("GET", "/api/report.pdf", "lang=hi", [], b"")
    assert status == 200 and body.startswith(b"%PDF")
    assert ["content-type", "application/pdf"] in headers
    status, _, body = bridge("GET", "/api/export.csv", "", [], b"")
    assert body.decode("utf-8").startswith("﻿Date")
