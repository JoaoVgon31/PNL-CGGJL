"""Interface de linha de comando do pipeline de stop-words."""

import sys
from pathlib import Path

import argparse

from .case_reader import read_all_case_ids, read_case
from .experiment.conditions import Condition
from .exporters.csv_exporter import export_pipeline_result
from .pipeline import process_case


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Converte casos clínicos em tabelas de nós e arestas.",
    )
    parser.add_argument("--cases", required=True, help="Caminho para cases.csv")
    parser.add_argument("--case-id", help="Identificador PMC..._NN de um único caso")
    parser.add_argument("--all-cases", action="store_true", help="Processa todos os casos do CSV")
    parser.add_argument(
        "--condition",
        default="BASELINE",
        choices=[condition.name for condition in Condition],
    )
    parser.add_argument("--wordlist", choices=["nltk_stopwords", "spacy_stopwords", "custom_clinical"], default=None)
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parent / "output"),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if not args.case_id and not args.all_cases:
        raise SystemExit("informe --case-id ou --all-cases")

    condition = Condition[args.condition]
    case_ids = [args.case_id] if args.case_id else read_all_case_ids(args.cases)

    for case_id in case_ids:
        try:
            case = read_case(args.cases, case_id)
            result = process_case(case, condition, args.wordlist)
        except (LookupError, ValueError) as error:
            print(f"erro ao processar {case_id}: {error}", file=sys.stderr)
            return 1

        nodes_path, edges_path = export_pipeline_result(result, args.output)
        print(f"{case_id}: nodes={nodes_path} edges={edges_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
