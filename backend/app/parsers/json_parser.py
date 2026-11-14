"""JSON: a list of records, or an object holding one (e.g. {"transactions": [...]})."""
from __future__ import annotations

import json

from ..models import ParsedRow
from ._decode import decode
from .tabular import parse_grid


def _find_records(node: object) -> list[dict] | None:
    if isinstance(node, list) and node and all(isinstance(x, dict) for x in node):
        return node
    if isinstance(node, dict):
        for value in node.values():
            found = _find_records(value)
            if found:
                return found
    return None


def parse(data: bytes) -> list[ParsedRow]:
    records = _find_records(json.loads(decode(data)))
    if not records:
        return []
    keys: list[str] = []
    for rec in records:
        keys.extend(k for k in rec if k not in keys)
    grid = [keys, *[[rec.get(k) for k in keys] for rec in records]]
    return parse_grid(grid) or []
