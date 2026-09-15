"""Exportação das tabelas de nós e arestas em CSV."""

import csv
from pathlib import Path

from ..pipeline import PipelineResult

NODE_COLUMNS = ("case_id", "node_id", "type", "label", "attributes")
EDGE_COLUMNS = ("case_id", "edge_id", "source_id", "target_id", "relation", "attributes")


def _write_csv(path: Path, columns: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def export_pipeline_result(result: PipelineResult, output_directory) -> tuple[Path, Path]:
    """Grava nodes.csv e edges.csv para o caso, no formato do contrato comum."""
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    stem = result.case.case_id

    nodes_path = output / f"{stem}-nodes.csv"
    edges_path = output / f"{stem}-edges.csv"

    _write_csv(nodes_path, NODE_COLUMNS, result.graph.node_rows())
    _write_csv(edges_path, EDGE_COLUMNS, result.graph.edge_rows())

    return nodes_path, edges_path
