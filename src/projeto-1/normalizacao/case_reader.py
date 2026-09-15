"""Leitura dos casos clínicos armazenados em CSV."""

import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path


_REQUIRED_COLUMNS = {
    "article_id",
    "age",
    "case_id",
    "case_text",
    "gender",
}


@dataclass(frozen=True)
class ClinicalCase:
    """Dados de entrada de um caso clínico."""

    article_id: str
    age: Decimal | None
    case_id: str
    case_text: str
    gender: str


def _parse_age(raw_age: str) -> Decimal | None:
    """Converte a idade do CSV, permitindo campo vazio."""
    cleaned_age = raw_age.strip()

    if not cleaned_age:
        return None

    try:
        return Decimal(cleaned_age)
    except InvalidOperation as error:
        raise ValueError(
            f"invalid age value: {raw_age!r}"
        ) from error


def read_case(
    csv_path: str | Path,
    case_id: str,
) -> ClinicalCase:
    """Lê exatamente um caso do CSV usando seu identificador."""
    path = Path(csv_path)

    if not isinstance(case_id, str) or not case_id.strip():
        raise ValueError("case_id must be a non-empty string")

    matches: list[ClinicalCase] = []

    with path.open(
        mode="r",
        encoding="utf-8-sig",
        newline="",
    ) as csv_file:
        reader = csv.DictReader(csv_file)
        fieldnames = set(reader.fieldnames or [])
        missing_columns = _REQUIRED_COLUMNS - fieldnames

        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(
                f"CSV is missing required columns: {missing}"
            )

        for row in reader:
            if row["case_id"].strip() != case_id:
                continue

            matches.append(
                ClinicalCase(
                    article_id=row["article_id"].strip(),
                    age=_parse_age(row["age"]),
                    case_id=row["case_id"].strip(),
                    case_text=row["case_text"],
                    gender=row["gender"].strip(),
                )
            )

    if not matches:
        raise LookupError(
            f"case_id not found: {case_id!r}"
        )

    if len(matches) > 1:
        raise ValueError(
            f"duplicate case_id in CSV: {case_id!r}"
        )

    return matches[0]