"""Pydantic schemas shared by the API and storage layers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date
from enum import Enum

from pydantic import BaseModel, Field


class TxType(str, Enum):
    DEBIT = "debit"
    CREDIT = "credit"


@dataclass
class ParsedRow:
    """A transaction as produced by a parser, before categorisation/storage."""

    description: str
    amount: float
    type: TxType
    date: Date | None = None
    category_hint: str | None = None


class TransactionIn(BaseModel):
    date: Date | None = None
    description: str = Field(min_length=1, max_length=200)
    amount: float = Field(gt=0)
    type: TxType = TxType.DEBIT
    category: str | None = None  # auto-detected when omitted


class TransactionUpdate(BaseModel):
    date: Date | None = None
    description: str | None = Field(default=None, min_length=1, max_length=200)
    amount: float | None = Field(default=None, gt=0)
    type: TxType | None = None
    category: str | None = None


class Transaction(BaseModel):
    id: int
    date: Date | None
    description: str
    amount: float
    type: TxType
    category: str
    source: str


class ImportRecord(BaseModel):
    id: int
    filename: str
    parser: str | None
    imported: int
    duplicates: int
    error: str | None
    created_at: str


class FileResult(BaseModel):
    filename: str
    parser: str | None
    imported: int
    duplicates: int
    error: str | None = None


class UploadResponse(BaseModel):
    files: list[FileResult]
    transactions: list[Transaction]


class CategoryTotal(BaseModel):
    category: str
    total: float
    count: int
    percent: float


class Summary(BaseModel):
    count: int
    total_credit: float
    total_debit: float
    net: float
    by_category: list[CategoryTotal]
