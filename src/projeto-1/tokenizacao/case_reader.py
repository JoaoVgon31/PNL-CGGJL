"""Leitura do arquivo cases.csv usando apenas a biblioteca padrão."""

from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
from pathlib import Path

from models import ClinicalCase


REQUIRED_COLUMNS = {"article_id", "age", "case_id", "case_text", "gender"}


def _parse_age(raw: str) -> Decimal | None:
    if not raw.strip():
        return None
    try:
        return Decimal(raw.strip())
    except InvalidOperation as error:
        raise ValueError(f"invalid age: {raw!r}") from error


def iter_cases(csv_path: str | Path):
    path = Path(csv_path)
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV is missing columns: {', '.join(sorted(missing))}")
        for row in reader:
            yield ClinicalCase(
                article_id=row["article_id"].strip(),
                age=_parse_age(row["age"]),
                case_id=row["case_id"].strip(),
                case_text=row["case_text"],
                gender=row["gender"].strip() or "Unknown",
            )


def read_case(csv_path: str | Path, case_id: str) -> ClinicalCase:
    matches = [case for case in iter_cases(csv_path) if case.case_id == case_id]
    if not matches:
        raise LookupError(f"case_id not found: {case_id!r}")
    if len(matches) > 1:
        raise ValueError(f"duplicate case_id: {case_id!r}")
    return matches[0]
