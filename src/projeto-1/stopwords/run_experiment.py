"""Roda o experimento completo sobre os 56 casos e grava o resumo agregado."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stopwords.case_reader import read_all_case_ids
from stopwords.experiment.report import summarize, write_summary
from stopwords.experiment.runner import run_experiment

CASES_PATH = Path(__file__).resolve().parents[3] / "sample" / "cases.csv"
OUTPUT_DIR = Path(__file__).resolve().parent / "experiment_output"


def main() -> int:
    case_ids = read_all_case_ids(CASES_PATH)
    print(f"running experiment over {len(case_ids)} cases...")
    results = run_experiment(str(CASES_PATH), case_ids)
    rows = summarize(results)
    csv_path, json_path = write_summary(rows, OUTPUT_DIR)
    print(f"summary: {csv_path}")
    for row in rows:
        print(row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
