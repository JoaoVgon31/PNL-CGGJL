"""Leitura de casos clínicos armazenados em cases.csv."""

import csv
from dataclasses import dataclass
from pathlib import Path

_REQUIRED_COLUMNS = {"article_id", "age", "case_id", "case_text", "gender"}


@dataclass(frozen=True)
class ClinicalCase:
    """Um caso clínico lido de cases.csv."""

    article_id: str
    age: str | None
    case_id: str
    case_text: str
    gender: str


def read_case(csv_path: str | Path, case_id: str) -> ClinicalCase:
    """Lê exatamente um caso do CSV usando seu identificador."""
    path = Path(csv_path)
    matches: list[ClinicalCase] = []

    with path.open(mode="r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        missing = _REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV is missing required columns: {', '.join(sorted(missing))}")

        for row in reader:
            if row["case_id"].strip() != case_id:
                continue
            matches.append(
                ClinicalCase(
                    article_id=row["article_id"].strip(),
                    age=row["age"].strip() or None,
                    case_id=row["case_id"].strip(),
                    case_text=row["case_text"],
                    gender=row["gender"].strip(),
                )
            )

    if not matches:
        raise LookupError(f"case_id not found: {case_id!r}")
    if len(matches) > 1:
        raise ValueError(f"duplicate case_id in CSV: {case_id!r}")
    return matches[0]


def read_all_case_ids(csv_path: str | Path) -> list[str]:
    """Lista todos os case_id do CSV, na ordem em que aparecem."""
    path = Path(csv_path)
    with path.open(mode="r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        return [row["case_id"].strip() for row in reader]
