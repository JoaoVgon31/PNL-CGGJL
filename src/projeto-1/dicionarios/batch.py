from __future__ import annotations

import argparse
import csv
from pathlib import Path

from crossval import cross_validate_case
from exporters import export_graph
from pipeline import load_gazetteers_by_category, process_case_from_csv

DEFAULT_OUTPUT_DIR = Path(__file__).parent / "output"


def run_batch(cases_csv: str | Path, metadata_csv: str | Path, output_dir: str | Path) -> None:
    cases_csv, metadata_csv, output_dir = Path(cases_csv), Path(metadata_csv), Path(output_dir)

    with cases_csv.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    gazetteers = load_gazetteers_by_category()
    summary_rows = []

    for row in rows:
        case_id, article_id = row["case_id"], row["article_id"]
        graph = process_case_from_csv(cases_csv, case_id, gazetteers)
        export_graph(graph, output_dir)

        result = cross_validate_case(graph, article_id, metadata_csv)
        summary_rows.append(
            {
                "case_id": case_id,
                "article_id": article_id,
                "nodes": len(graph.nodes),
                "edges": len(graph.edges),
                "same_as_edges": sum(1 for e in graph.edges if e.relation == "SAME_AS"),
                "case_concepts": len(result.case_concept_terms),
                "article_mesh_terms": len(result.article_mesh_terms),
                "overlap": len(result.overlap_terms),
                "overlap_ratio_of_article_terms": (
                    f"{result.overlap_ratio_of_article_terms:.3f}"
                    if result.overlap_ratio_of_article_terms is not None
                    else ""
                ),
            }
        )

    summary_path = output_dir / "_crossval_summary.csv"
    with summary_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"processados {len(rows)} casos -> {output_dir}")
    print(f"resumo da validação cruzada -> {summary_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", required=True)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--output", default=DEFAULT_OUTPUT_DIR)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_batch(args.cases, args.metadata, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
