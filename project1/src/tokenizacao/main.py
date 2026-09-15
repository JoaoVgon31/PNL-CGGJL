"""Interface de linha de comando da estratégia de tokenização."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from case_reader import read_case
from evaluation import compare_case, compare_sample
from pipeline import process_case
from serialization import export_pipeline_result, write_json
from tokenizers import TOKENIZERS, get_tokenizer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Tokeniza um caso clínico e produz as tabelas do grafo.",
    )
    parser.add_argument("--cases", required=True, help="caminho para cases.csv")
    parser.add_argument("--case-id", help="identificador no formato PMC..._NN")
    parser.add_argument(
        "--tokenizer",
        choices=tuple(TOKENIZERS),
        default="clinical_regex",
        help="tokenizador usado para gerar o grafo",
    )
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parent / "output"),
        help="diretório de saída",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="compara os tokenizadores no caso selecionado",
    )
    parser.add_argument(
        "--evaluate-sample",
        action="store_true",
        help="mede os três tokenizadores em todo o cases.csv",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output = Path(args.output)

    if args.evaluate_sample:
        destination = write_json(output / "sample-comparison.json", compare_sample(args.cases))
        print(f"sample comparison: {destination}")
        if not args.case_id:
            return 0

    if not args.case_id:
        raise SystemExit("--case-id is required unless --evaluate-sample is used")

    case = read_case(args.cases, args.case_id)
    result = process_case(case, get_tokenizer(args.tokenizer))
    paths = export_pipeline_result(result, output)
    print(f"tokens: {paths.tokens}")
    print(f"nodes: {paths.nodes}")
    print(f"edges: {paths.edges}")
    print(f"graph: {paths.graph}")
    print(f"slide graph: {paths.slide_graph}")

    if args.compare:
        destination = write_json(
            output / f"{case.case_id}-comparison.json",
            compare_case(case),
        )
        print(f"comparison: {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
