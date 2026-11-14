import io
import json
from datetime import date

import pytest
from openpyxl import Workbook

from app.models import TxType
from app.parsers import UnsupportedFormat, parse_file
from tests.conftest import make_pdf


def test_csv_debit_credit_columns_with_preamble():
    data = (
        "HDFC Bank Statement\nAccount: XXXX1234\n\n"
        "Date,Narration,Chq/Ref No,Withdrawal Amt,Deposit Amt,Closing Balance\n"
        "01/10/2025,UPI-SWIGGY-swiggy@icici,4512,\"1,250.00\",,8750.00\n"
        "02/10/2025,NEFT CR-DAD POCKET MONEY,7781,,5000.00,13750.00\n"
        ",Closing Balance,,,,13750.00\n"
    ).encode()
    name, rows = parse_file("hdfc.csv", data)
    assert name == "csv"
    assert len(rows) == 2
    assert rows[0].amount == 1250.0 and rows[0].type == TxType.DEBIT
    assert rows[0].date == date(2025, 10, 1)
    assert rows[1].amount == 5000.0 and rows[1].type == TxType.CREDIT


def test_csv_signed_amount_and_semicolon():
    data = "Date;Description;Amount\n2025-10-05;Uber trip;-340.50\n2025-10-06;Salary;20000\n".encode()
    _, rows = parse_file("x.csv", data)
    assert [(r.type, r.amount) for r in rows] == [(TxType.DEBIT, 340.5), (TxType.CREDIT, 20000.0)]


def test_csv_amount_with_type_column():
    data = b"Txn Date,Details,Amount (INR),Dr/Cr\n05 Oct 2025,Jio recharge,239,DR\n06 Oct 2025,Refund,99,CR\n"
    _, rows = parse_file("x.csv", data)
    assert rows[0].type == TxType.DEBIT and rows[0].date == date(2025, 10, 5)
    assert rows[1].type == TxType.CREDIT


def test_excel():
    wb = Workbook()
    ws = wb.active
    ws.append(["My expenses"])
    ws.append(["Date", "Description", "Debit", "Credit"])
    ws.append([date(2025, 10, 1), "Dominos pizza", 450, None])
    ws.append([date(2025, 10, 2), "Scholarship", None, 10000])
    buf = io.BytesIO()
    wb.save(buf)
    name, rows = parse_file("book.xlsx", buf.getvalue())
    assert name == "excel" and len(rows) == 2
    assert rows[0].date == date(2025, 10, 1) and rows[1].type == TxType.CREDIT


def test_json_nested():
    data = json.dumps({"data": {"transactions": [
        {"date": "2025-10-01", "merchant": "Amazon", "amount": -899, "category": "Shopping"},
        {"date": "2025-10-02", "merchant": "Cashback", "amount": 50},
    ]}}).encode()
    _, rows = parse_file("export.json", data)
    assert rows[0].category_hint == "Shopping" and rows[0].type == TxType.DEBIT
    assert rows[1].type == TxType.CREDIT


def test_txt_phonepe_style():
    data = (
        "Oct 01, 2025  Paid to Zomato  DEBIT  ₹340\n"
        "Transaction ID T2510011234567890\n"
        "Oct 02, 2025  Received from Ravi  CREDIT  ₹500\n"
    ).encode()
    name, rows = parse_file("phonepe.txt", data)
    assert name == "text"
    assert [(r.amount, r.type) for r in rows] == [(340.0, TxType.DEBIT), (500.0, TxType.CREDIT)]
    assert rows[0].date == date(2025, 10, 1)
    assert "Zomato" in rows[0].description


def test_pdf_text_statement():
    pdf = make_pdf([
        "SBI Account Statement",
        "Date Description Debit Credit Balance",
        "01/10/2025 UPI/DR/RAPIDO 120.00 4880.00",
        "03/10/2025 UPI/CR/MOM 2000.00 Cr 6880.00",
    ])
    name, rows = parse_file("sbi.pdf", pdf)
    assert name == "pdf"
    assert [(r.amount, r.type) for r in rows] == [(120.0, TxType.DEBIT), (2000.0, TxType.CREDIT)]


def test_pdf_detected_by_magic_bytes():
    name, _ = parse_file("statement.download", make_pdf(["01/10/2025 Tea 20.00 100.00"]))
    assert name == "pdf"


def test_unsupported_binary():
    with pytest.raises(UnsupportedFormat):
        parse_file("photo.heic", b"\x00\x01\xff\xfe\x80garbage")
