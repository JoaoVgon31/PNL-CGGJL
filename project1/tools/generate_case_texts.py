"""Gera project1/data/case_texts.csv a partir de sample/cases.csv (local).

sample/ não é versionado (ver .gitignore e project1/README.md), então este
script só funciona em quem já tem a amostra do MultiCaRe baixada localmente.
O resultado (case_id, case_text) é commitado especificamente para o
visualizador poder mostrar o texto completo do caso mesmo num runner de CI
sem acesso a sample/. Rodar de novo e recommitar sempre que a amostra local
mudar (novos casos, texto corrigido).
"""

import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CASE_TEXTS_COLUMNS = ("case_id", "case_text")


def generate(cases_csv: Path, output_csv: Path) -> int:
    with cases_csv.open(encoding="utf-8", newline="") as handle:
        rows = [
            {"case_id": row["case_id"], "case_text": row["case_text"]}
            for row in csv.DictReader(handle)
        ]
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CASE_TEXTS_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


if __name__ == "__main__":
    cases_csv_path = PROJECT_ROOT.parent / "sample" / "cases.csv"
    output_csv_path = PROJECT_ROOT / "data" / "case_texts.csv"
    if not cases_csv_path.exists():
        print(
            f"não encontrado: {cases_csv_path} (amostra local necessária, não versionada)",
            file=sys.stderr,
        )
        raise SystemExit(1)
    written = generate(cases_csv_path, output_csv_path)
    print(f"{output_csv_path.relative_to(PROJECT_ROOT.parent)}: {written} casos")
