"""REST API routes."""
from __future__ import annotations

import csv
import io
from collections import defaultdict

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response, StreamingResponse

from . import parsers
from .categorizer import CATEGORIES, categorize, merchant_key
from .models import (
    CategoryTotal,
    FileResult,
    ImportRecord,
    Summary,
    Transaction,
    TransactionIn,
    TransactionUpdate,
    TxType,
    UploadResponse,
)
from .report import build_report
from .db import Store

MAX_UPLOAD_BYTES = 20 * 1024 * 1024

router = APIRouter(prefix="/api")

_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/formats")
def formats() -> dict[str, list[str]]:
    return {"extensions": parsers.supported_extensions()}


@router.get("/categories")
def categories() -> list[str]:
    return CATEGORIES


# ---- upload -----------------------------------------------------------------
@router.post("/upload", response_model=UploadResponse)
async def upload(files: list[UploadFile] = File(...), store: Store = Depends(get_store)):
    results: list[FileResult] = []
    imported: list[Transaction] = []
    learned = store.learned_rules()

    for upload_file in files:
        name = upload_file.filename or "upload"
        data = await upload_file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            results.append(FileResult(filename=name, parser=None, imported=0, duplicates=0,
                                      error="File is larger than 20 MB."))
            continue
        try:
            parser_name, rows = parsers.parse_file(name, data)
        except Exception as exc:  # each file fails independently
            error = str(exc) or exc.__class__.__name__
            store.finish_import(store.start_import(name, None), 0, 0, error)
            results.append(FileResult(filename=name, parser=None, imported=0, duplicates=0,
                                      error=error))
            continue

        import_id = store.start_import(name, parser_name)
        count = dupes = 0
        for row in rows:
            if row.amount <= 0:
                continue
            if store.exists(row.date, row.description, row.amount, row.type):
                dupes += 1
                continue
            category = categorize(row.description, row.type, learned, row.category_hint)
            imported.append(store.add(row.date, row.description, row.amount, row.type,
                                      category, source=parser_name, import_id=import_id))
            count += 1
        error = None if rows else "No transactions found in this file."
        store.finish_import(import_id, count, dupes, error)
        results.append(FileResult(filename=name, parser=parser_name, imported=count,
                                  duplicates=dupes, error=error))
    return UploadResponse(files=results, transactions=imported)


@router.get("/imports", response_model=list[ImportRecord])
def list_imports(store: Store = Depends(get_store)):
    """Upload history, newest first."""
    return store.imports()


# ---- transactions -----------------------------------------------------------
@router.get("/transactions", response_model=list[Transaction])
def list_transactions(
    category: str | None = None,
    type: TxType | None = Query(default=None),
    q: str | None = None,
    store: Store = Depends(get_store),
):
    return store.list(category=category, tx_type=type, q=q)


@router.post("/transactions", response_model=Transaction, status_code=201)
def create_transaction(body: TransactionIn, store: Store = Depends(get_store)):
    description = body.description.strip()
    if body.category:
        _check_category(body.category)
        category = body.category
        if body.type == TxType.DEBIT:
            store.learn(merchant_key(description), category)
    else:
        category = categorize(description, body.type, store.learned_rules())
    return store.add(body.date, description, round(body.amount, 2), body.type, category, "manual")


@router.patch("/transactions/{tx_id}", response_model=Transaction)
def update_transaction(tx_id: int, body: TransactionUpdate, store: Store = Depends(get_store)):
    current = store.get(tx_id)
    if not current:
        raise HTTPException(404, "Transaction not found")
    fields = body.model_dump(exclude_unset=True)
    if "category" in fields:
        _check_category(fields["category"])
    updated = store.update(tx_id, fields)
    assert updated is not None

    # Teach the categoriser and apply to other uncorrected rows from the same merchant.
    if "category" in fields and fields["category"] != current.category and updated.type == TxType.DEBIT:
        key = merchant_key(updated.description)
        store.learn(key, updated.category)
        same = [t.id for t in store.list(tx_type=TxType.DEBIT)
                if t.id != tx_id and merchant_key(t.description) == key]
        store.recategorize(same, updated.category)
    return updated


@router.delete("/transactions/{tx_id}", status_code=204)
def delete_transaction(tx_id: int, store: Store = Depends(get_store)):
    if not store.delete(tx_id):
        raise HTTPException(404, "Transaction not found")


@router.delete("/transactions")
def clear_transactions(store: Store = Depends(get_store)) -> dict[str, int]:
    return {"deleted": store.clear()}


# ---- reports ----------------------------------------------------------------
def compute_summary(txs: list[Transaction]) -> Summary:
    credit = sum(t.amount for t in txs if t.type == TxType.CREDIT)
    debit = sum(t.amount for t in txs if t.type == TxType.DEBIT)
    totals: dict[str, list[float]] = defaultdict(lambda: [0.0, 0])
    for t in txs:
        if t.type == TxType.DEBIT:
            totals[t.category][0] += t.amount
            totals[t.category][1] += 1
    by_category = sorted(
        (CategoryTotal(category=c, total=round(v[0], 2), count=int(v[1]),
                       percent=round(v[0] / debit * 100, 1) if debit else 0.0)
         for c, v in totals.items()),
        key=lambda x: x.total, reverse=True,
    )
    return Summary(count=len(txs), total_credit=round(credit, 2), total_debit=round(debit, 2),
                   net=round(credit - debit, 2), by_category=by_category)


@router.get("/summary", response_model=Summary)
def summary(store: Store = Depends(get_store)):
    return compute_summary(store.list())


@router.get("/report.pdf")
def report_pdf(lang: str = Query(default="en", pattern="^(en|te|hi)$"),
               store: Store = Depends(get_store)):
    txs = store.list()
    pdf = build_report(compute_summary(txs), txs, lang)
    return Response(
        content=pdf, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="spendyfrd-report-{lang}.pdf"'},
    )


@router.get("/export.csv")
def export_csv(store: Store = Depends(get_store)):
    buf = io.StringIO()
    buf.write("﻿")  # BOM so Excel opens UTF-8 (₹) correctly
    writer = csv.writer(buf)
    writer.writerow(["Date", "Description", "Category", "Type", "Amount", "Source"])
    for t in store.list():
        writer.writerow([t.date or "", t.description, t.category, t.type.value, t.amount, t.source])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="spendyfrd-transactions.csv"'},
    )


def _check_category(category: str) -> None:
    if category not in CATEGORIES:
        raise HTTPException(422, f"Unknown category '{category}'")
