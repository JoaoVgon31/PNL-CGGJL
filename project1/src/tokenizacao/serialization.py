"""Escrita das tabelas, tokens e relatórios JSON."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from mermaid_export import render_full_graph, render_slide_graph
from pipeline import PipelineResult


NODE_COLUMNS = ("case_id", "node_id", "type", "label", "attributes")
EDGE_COLUMNS = (
    "case_id", "edge_id", "source_id", "target_id", "relation", "attributes",
)
TOKEN_COLUMNS = ("case_id", "tokenizer", "index", "text", "kind", "start", "end")


@dataclass(frozen=True)
class OutputPaths:
    nodes: Path
    edges: Path
    tokens: Path
    graph: Path
    slide_graph: Path


def _write_csv(path: Path, columns, rows) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def export_pipeline_result(result: PipelineResult, output_directory) -> OutputPaths:
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    stem = result.case.case_id
    paths = OutputPaths(
        nodes=output / f"{stem}-nodes.csv",
        edges=output / f"{stem}-edges.csv",
        tokens=output / f"{stem}-tokens.csv",
        graph=output / f"{stem}-graph.md",
        slide_graph=output / f"{stem}-graph-slide.md",
    )
    _write_csv(paths.nodes, NODE_COLUMNS, result.graph.node_rows())
    _write_csv(paths.edges, EDGE_COLUMNS, result.graph.edge_rows())
    token_rows = [
        {
            "case_id": result.case.case_id,
            "tokenizer": result.tokenizer_name,
            "index": token.index,
            "text": token.text,
            "kind": token.kind,
            "start": token.start,
            "end": token.end,
        }
        for token in result.tokens
    ]
    _write_csv(paths.tokens, TOKEN_COLUMNS, token_rows)
    paths.graph.write_text(render_full_graph(result), encoding="utf-8")
    paths.slide_graph.write_text(render_slide_graph(result), encoding="utf-8")
    return paths


def write_json(path, value) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return destination
