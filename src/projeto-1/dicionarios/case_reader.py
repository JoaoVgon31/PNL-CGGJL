from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

_REQUIRED_COLUMNS = {"article_id", "age", "case_id", "case_text", "gender"}


@dataclass(frozen=True)
class ClinicalCase:
    article_id: str
    age: str
    case_id: str
    case_text: str
    gender: str


def read_case(csv_path: str | Path, case_id: str) -> ClinicalCase:
    path = Path(csv_path)

    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        missing = _REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV sem colunas obrigatórias: {sorted(missing)}")

        matches = [row for row in reader if row["case_id"].strip() == case_id]

    if not matches:
        raise LookupError(f"case_id não encontrado: {case_id!r}")
    if len(matches) > 1:
        raise ValueError(f"case_id duplicado no CSV: {case_id!r}")

    row = matches[0]
    return ClinicalCase(
        article_id=row["article_id"].strip(),
        age=row["age"].strip(),
        case_id=row["case_id"].strip(),
        case_text=row["case_text"],
        gender=row["gender"].strip(),
    )
