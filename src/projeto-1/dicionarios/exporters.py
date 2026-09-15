from __future__ import annotations

import csv
from pathlib import Path

from core.graph import GraphBuilder

NODE_COLUMNS = ("case_id", "node_id", "type", "label", "attributes")
EDGE_COLUMNS = ("case_id", "edge_id", "source_id", "target_id", "relation", "attributes")


def _write_csv(path: Path, columns: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def export_graph(graph: GraphBuilder, output_dir: str | Path) -> tuple[Path, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    nodes_path = output / f"{graph.case_id}-nodes.csv"
    edges_path = output / f"{graph.case_id}-edges.csv"
    _write_csv(nodes_path, NODE_COLUMNS, graph.node_rows())
    _write_csv(edges_path, EDGE_COLUMNS, graph.edge_rows())
    return nodes_path, edges_path
