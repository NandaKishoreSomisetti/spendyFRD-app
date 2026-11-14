"""Transaction categoriser.

Order of precedence:
1. Credits are always "Income".
2. Learned rules (saved when the user re-categorises a transaction).
3. Keyword rules below. Matching is whole-word, so "vi" does not match "service".
4. "Other".
"""
from __future__ import annotations

import re
from collections.abc import Mapping

from .models import TxType

INCOME = "Income"
OTHER = "Other"

KEYWORD_RULES: dict[str, list[str]] = {
    "Food & Dining": [
        "zomato", "swiggy", "mess", "canteen", "cafe", "café", "tea", "coffee", "food",
        "restaurant", "bakery", "dominos", "domino's", "pizza", "burger", "biryani",
        "snack", "snacks", "dhaba", "maggi", "juice", "shawarma", "kfc", "mcdonald",
        "mcdonalds", "eats", "starbucks", "chai", "tiffin", "hotel",
    ],
    "Groceries": [
        "blinkit", "zepto", "instamart", "bigbasket", "dmart", "grocery", "groceries",
        "kirana", "supermarket", "vegetables", "milk", "jiomart",
    ],
    "Travel & Transport": [
        "uber", "ola", "rapido", "irctc", "train", "bus", "auto", "metro", "flight",
        "indigo", "petrol", "fuel", "shuttle", "redbus", "toll", "chalo", "fastag",
        "cab", "taxi", "airlines", "makemytrip", "goibibo",
    ],
    "Education": [
        "book", "books", "stationery", "print", "xerox", "course", "udemy", "exam",
        "tuition", "library", "notebook", "lab", "college", "coursera", "nptel",
        "university", "school", "semester", "fees",
    ],
    "Bills & Utilities": [
        "jio", "airtel", "vodafone", "bsnl", "recharge", "wifi", "electricity", "bill",
        "broadband", "dth", "water", "rent", "cylinder", "gas", "postpaid", "prepaid",
    ],
    "Subscriptions & Entertainment": [
        "netflix", "spotify", "prime", "hotstar", "subscription", "youtube", "bookmyshow",
        "pvr", "inox", "movie", "cinema", "gaming", "steam", "playstation",
    ],
    "Shopping": [
        "amazon", "flipkart", "myntra", "zudio", "mall", "clothes", "decathlon",
        "ajio", "nykaa", "lenskart", "shoes", "fashion", "trends", "h&m", "croma",
        "reliance digital", "meesho", "store",
    ],
    "Health": [
        "pharmacy", "medical", "medicals", "apollo", "hospital", "clinic", "doctor",
        "medicine", "pharmeasy", "1mg", "netmeds", "gym", "fitness", "cult",
    ],
    "Transfers & Cash": [
        "atm", "cash withdrawal", "neft", "imps", "rtgs", "self transfer", "transfer",
    ],
}

CATEGORIES: list[str] = [*KEYWORD_RULES.keys(), OTHER, INCOME]


def _compile(keywords: list[str]) -> re.Pattern[str]:
    alternatives = "|".join(re.escape(k) for k in sorted(keywords, key=len, reverse=True))
    return re.compile(rf"(?<![a-z0-9])(?:{alternatives})(?![a-z0-9])", re.IGNORECASE)


_COMPILED = [(cat, _compile(words)) for cat, words in KEYWORD_RULES.items()]

_NOISE = re.compile(
    r"\b(upi|imps|neft|rtgs|pos|ach|txn|ref|no|paid|to|from|sent|received|payment|"
    r"debit|credit|dr|cr|via|transfer|mb|ib|vpa)\b|[^a-z& ]",
    re.IGNORECASE,
)


def _words(description: str) -> list[str]:
    text = description.lower().replace("@", " ").replace("/", " ")
    text = _NOISE.sub(" ", text)
    return [w for w in text.split() if len(w) > 1]


def merchant_key(description: str) -> str:
    """Stable key for a merchant: lowercase, no IDs or rail prefixes, first 3 words.

    'UPI/DR/4512398/ZOMATO LTD/zomato@hdfc' -> 'zomato ltd zomato'
    """
    return " ".join(_words(description)[:3])


def categorize(
    description: str,
    tx_type: TxType,
    learned: Mapping[str, str] | None = None,
    hint: str | None = None,
) -> str:
    if tx_type == TxType.CREDIT:
        return INCOME

    if learned:
        key = merchant_key(description)
        if key and key in learned:
            return learned[key]
        haystack = f" {' '.join(_words(description))} "
        for learned_key, category in learned.items():
            if learned_key and f" {learned_key} " in haystack:
                return category

    if hint:
        for category in CATEGORIES:
            if hint.strip().lower() == category.lower():
                return category

    for category, pattern in _COMPILED:
        if pattern.search(description):
            return category
    return OTHER
