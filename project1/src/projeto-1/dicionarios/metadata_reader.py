from __future__ import annotations

import csv
from pathlib import Path


def parse_bracket_list(raw: str) -> list[str]:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        raw = raw[1:-1]
    if not raw.strip():
        return []

    items: list[str] = []
    current: list[str] = []
    in_quote = False
    quote_char = ""
    escape = False

    for ch in raw:
        if in_quote:
            if escape:
                current.append(ch)
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote_char:
                in_quote = False
            else:
                current.append(ch)
        elif ch in ("'", '"'):
            in_quote, quote_char = True, ch
        elif ch == ",":
            items.append("".join(current))
            current = []
        else:
            current.append(ch)

    if current:
        items.append("".join(current))

    return [item.strip() for item in items]


def read_metadata_row(csv_path: str | Path, article_id: str) -> dict[str, str] | None:
    path = Path(csv_path)
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if row["article_id"].strip() == article_id:
                return row
    return None


def base_term(term: str) -> str:
    return term.split(" / ")[0].strip()
