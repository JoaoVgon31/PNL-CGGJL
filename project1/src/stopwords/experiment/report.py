"""Agrega os resultados do experimento num resumo por condição x lista."""

import csv
import json
from collections import defaultdict
from pathlib import Path

from .runner import VariantResult


def summarize(results: list[VariantResult]) -> list[dict]:
    """Agrega os VariantResult em totais por (condição, lista), com o pior caso de cada."""
    totals: dict[tuple[str, str], dict] = defaultdict(lambda: {
        "nodes_lost": 0, "nodes_gained": 0, "polarity_changed": 0,
        "edges_lost": 0, "edges_gained": 0,
        "worst_case_id": None, "worst_case_polarity_changed": -1,
    })

    for result in results:
        key = (result.condition.name, result.wordlist)
        bucket = totals[key]
        bucket["nodes_lost"] += result.diff.nodes_lost
        bucket["nodes_gained"] += result.diff.nodes_gained
        bucket["polarity_changed"] += result.diff.polarity_changed
        bucket["edges_lost"] += result.diff.edges_lost
        bucket["edges_gained"] += result.diff.edges_gained
        if result.diff.polarity_changed > bucket["worst_case_polarity_changed"]:
            bucket["worst_case_polarity_changed"] = result.diff.polarity_changed
            bucket["worst_case_id"] = result.diff.case_id

    rows = []
    for (condition, wordlist), bucket in sorted(totals.items()):
        rows.append({"condition": condition, "wordlist": wordlist, **bucket})
    return rows


def write_summary(rows: list[dict], output_directory) -> tuple[Path, Path]:
    """Grava o resumo em summary.csv e summary.json."""
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)

    csv_path = output / "summary.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    json_path = output / "summary.json"
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    return csv_path, json_path
