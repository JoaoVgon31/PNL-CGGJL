from __future__ import annotations

import argparse
from pathlib import Path

from exporters import export_graph
from pipeline import process_case_from_csv

DEFAULT_OUTPUT_DIR = Path(__file__).parent / "output"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output", default=DEFAULT_OUTPUT_DIR)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    graph = process_case_from_csv(args.cases, args.case_id)
    nodes_path, edges_path = export_graph(graph, args.output)
    print(f"nodes: {nodes_path}")
    print(f"edges: {edges_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
