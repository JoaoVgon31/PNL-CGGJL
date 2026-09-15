"""Exportação das tabelas e do relatório de impacto."""

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from ..pipeline import PipelineResult
from .mermaid import render_mermaid_markdown


NODE_COLUMNS = ("case_id", "node_id", "type", "label", "attributes")
EDGE_COLUMNS = (
    "case_id",
    "edge_id",
    "source_id",
    "target_id",
    "relation",
    "attributes",
)


@dataclass(frozen=True)
class OutputPaths:
    """Arquivos gerados para um caso processado."""

    nodes: Path
    edges: Path
    impact: Path
    graph: Path


def _write_csv(
    path: Path,
    columns: tuple[str, ...],
    rows: list[dict[str, str]],
) -> None:
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def export_pipeline_result(
    result: PipelineResult,
    output_directory: str | Path,
) -> OutputPaths:
    """Grava nós, arestas e impacto da normalização."""
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    stem = result.case.case_id

    paths = OutputPaths(
        nodes=output / f"{stem}-nodes.csv",
        edges=output / f"{stem}-edges.csv",
        impact=output / f"{stem}-impact.json",
        graph=output / f"{stem}-graph.md",
    )
    _write_csv(paths.nodes, NODE_COLUMNS, result.graph.node_rows())
    _write_csv(paths.edges, EDGE_COLUMNS, result.graph.edge_rows())

    impact: dict[str, object] = result.graph.normalization_impact().to_dict()
    impact["case_id"] = result.case.case_id
    impact["acronyms"] = result.graph.normalizer.acronym_definitions

    with paths.impact.open("w", encoding="utf-8") as output_file:
        json.dump(impact, output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")

    paths.graph.write_text(
        render_mermaid_markdown(result.graph),
        encoding="utf-8",
    )

    return paths
