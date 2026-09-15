from __future__ import annotations

import csv
from pathlib import Path

from anatomical_site_terms import ANATOMICAL_SITE_TERMS

OUTPUT_PATH = Path(__file__).parent / "gazetteer" / "anatomical_site_gazetteer.csv"
COLUMNS = ("term", "code", "preferred_term", "category")


def build_rows() -> list[dict[str, str]]:
    rows = []
    for index, (preferred_term, synonyms) in enumerate(ANATOMICAL_SITE_TERMS, start=1):
        code = f"ANAT{index:03d}"
        for term in [preferred_term, *synonyms]:
            rows.append(
                {
                    "term": term,
                    "code": code,
                    "preferred_term": preferred_term,
                    "category": "anatomical_site",
                }
            )
    return rows


def main() -> None:
    rows = build_rows()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{len(rows)} linhas -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
