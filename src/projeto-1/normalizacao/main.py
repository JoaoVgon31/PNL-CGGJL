"""Interface de linha de comando do pipeline de normalização."""

import argparse
from collections.abc import Sequence
from pathlib import Path

from .exporters.csv_exporter import export_pipeline_result
from .pipeline import process_case_from_csv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Converte um caso clínico em tabelas de nós e arestas.",
    )
    parser.add_argument("--cases", required=True, help="Caminho para cases.csv")
    parser.add_argument("--case-id", required=True, help="Identificador PMC..._NN")
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parent / "output"),
        help="Diretório de saída",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = process_case_from_csv(args.cases, args.case_id)
    paths = export_pipeline_result(result, args.output)

    print(f"nodes: {paths.nodes}")
    print(f"edges: {paths.edges}")
    print(f"impact: {paths.impact}")
    print(f"graph: {paths.graph}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
