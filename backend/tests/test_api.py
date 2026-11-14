import pytest
from fastapi.testclient import TestClient

from app import api
from app.main import app
from tests.conftest import make_pdf


@pytest.fixture()
def client(store):
    app.dependency_overrides[api.get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


CSV = b"Date,Description,Amount,Type\n01/10/2025,Swiggy dinner,300,debit\n02/10/2025,Pocket money,5000,credit\n03/10/2025,RAMESH STORES,150,debit\n"


def test_upload_categorises_and_dedupes(client):
    r = client.post("/api/upload", files=[("files", ("s.csv", CSV, "text/csv"))])
    assert r.status_code == 200
    body = r.json()
    assert body["files"][0]["imported"] == 3
    cats = {t["description"]: t["category"] for t in body["transactions"]}
    assert cats == {"Swiggy dinner": "Food & Dining", "Pocket money": "Income", "RAMESH STORES": "Other"}

    again = client.post("/api/upload", files=[("files", ("s.csv", CSV, "text/csv"))]).json()
    assert again["files"][0] == {"filename": "s.csv", "parser": "csv", "imported": 0,
                                 "duplicates": 3, "error": None}


def test_multi_file_upload_isolates_errors(client):
    r = client.post("/api/upload", files=[
        ("files", ("ok.pdf", make_pdf(["01/10/2025 Uber ride 200.00 800.00"]), "application/pdf")),
        ("files", ("bad.bin", b"\x00\xff\xfe\x80", "application/octet-stream")),
    ]).json()
    assert r["files"][0]["imported"] == 1
    assert r["files"][1]["error"]


def test_manual_entry_and_summary(client):
    r = client.post("/api/transactions", json={"description": "Auto to college", "amount": 40})
    assert r.status_code == 201 and r.json()["category"] == "Travel & Transport"
    client.post("/api/transactions", json={"description": "Gift", "amount": 1000, "type": "credit"})
    s = client.get("/api/summary").json()
    assert s["total_debit"] == 40 and s["total_credit"] == 1000 and s["net"] == 960
    assert s["by_category"][0] == {"category": "Travel & Transport", "total": 40, "count": 1, "percent": 100.0}


def test_recategorise_learns_and_applies(client):
    client.post("/api/upload", files=[("files", ("s.csv", CSV, "text/csv"))])
    txs = client.get("/api/transactions").json()
    ramesh = next(t for t in txs if t["description"] == "RAMESH STORES")
    r = client.patch(f"/api/transactions/{ramesh['id']}", json={"category": "Groceries"})
    assert r.json()["category"] == "Groceries"
    # future entries from the same merchant get the learned category
    new = client.post("/api/transactions", json={"description": "Ramesh Stores", "amount": 80}).json()
    assert new["category"] == "Groceries"


def test_filters_delete_export(client):
    client.post("/api/upload", files=[("files", ("s.csv", CSV, "text/csv"))])
    assert len(client.get("/api/transactions", params={"type": "credit"}).json()) == 1
    assert len(client.get("/api/transactions", params={"q": "swiggy"}).json()) == 1
    tx_id = client.get("/api/transactions").json()[0]["id"]
    assert client.delete(f"/api/transactions/{tx_id}").status_code == 204
    assert client.delete(f"/api/transactions/{tx_id}").status_code == 404
    csv_text = client.get("/api/export.csv").text
    assert csv_text.startswith("﻿Date,Description")
    assert client.delete("/api/transactions").json() == {"deleted": 2}


def test_validation(client):
    assert client.post("/api/transactions", json={"description": "x", "amount": -5}).status_code == 422
    assert client.post("/api/transactions",
                       json={"description": "x", "amount": 5, "category": "Nope"}).status_code == 422


def test_pdf_report_all_languages(client):
    client.post("/api/upload", files=[("files", ("s.csv", CSV, "text/csv"))])
    for lang in ("en", "te", "hi"):
        r = client.get("/api/report.pdf", params={"lang": lang})
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.content.startswith(b"%PDF")
    assert client.get("/api/report.pdf", params={"lang": "xx"}).status_code == 422


def test_pdf_report_empty(client):
    assert client.get("/api/report.pdf").content.startswith(b"%PDF")


def test_import_history(client):
    client.post("/api/upload", files=[("files", ("s.csv", CSV, "text/csv")),
                                      ("files", ("bad.bin", b"\x00\xff\xfe\x80", "application/octet-stream"))])
    hist = client.get("/api/imports").json()
    assert [h["filename"] for h in hist] == ["bad.bin", "s.csv"]
    assert hist[1]["imported"] == 3 and hist[0]["error"]


def test_locales_served_and_complete(client):
    en = client.get("/locales/en.json").json()
    for lang in ("te", "hi"):
        other = client.get(f"/locales/{lang}.json").json()
        for section in ("ui", "categories", "report"):
            assert set(other[section]) == set(en[section]), (lang, section)
    assert set(en["categories"]) == set(client.get("/api/categories").json())
