"""Renderização do grafo em Markdown com diagrama Mermaid."""

from html import escape

from ..core.graph import GraphBuilder
from ..core.models import Node


_NODE_STYLES = {
    "Patient": ("#fef3c7", "#d97706"),
    "History": ("#e0e7ff", "#4338ca"),
    "Symptom": ("#fee2e2", "#b91c1c"),
    "Finding": ("#fce7f3", "#be185d"),
    "Exam": ("#dbeafe", "#1d4ed8"),
    "ExamResult": ("#cffafe", "#0e7490"),
    "Diagnosis": ("#dcfce7", "#15803d"),
    "Treatment": ("#fef9c3", "#a16207"),
    "Medication": ("#ffedd5", "#c2410c"),
    "AnatomicalSite": ("#ede9fe", "#6d28d9"),
    "Outcome": ("#f3e8ff", "#7e22ce"),
    "Concept": ("#f3f4f6", "#4b5563"),
}

_HORIZONTAL_LAYOUT = (
    '%%{init: {"flowchart": {"wrappingWidth": 300, '
    '"nodeSpacing": 35, "rankSpacing": 140}}}%%'
)


def _patient_summary(node: Node) -> str:
    age = node.attributes.get("age")
    age_unit = str(node.attributes.get("age_unit", "")).casefold()
    gender = node.attributes.get("gender")
    unit = {
        "years": "yo",
        "year": "yo",
        "months": "mo",
        "month": "mo",
        "weeks": "wk",
        "week": "wk",
        "days": "d",
        "day": "d",
    }.get(age_unit, age_unit)

    demographics = []
    if age is not None and age != "":
        demographics.append(f"{age}{unit}")
    if gender:
        demographics.append(str(gender))

    parts = ["<b>Patient</b>"]
    if demographics:
        parts.append(escape(" ".join(demographics)))
    return "<br/>".join(parts)


def _exam_result_summary(node: Node) -> str:
    parts = [escape(node.label)]
    low = node.attributes.get("reference_range_low")
    high = node.attributes.get("reference_range_high")
    unit = node.attributes.get("unit")
    if low is not None and high is not None:
        suffix = f" {unit}" if unit else ""
        parts.append(escape(f"ref {low}-{high}{suffix}"))
    return "<br/>".join(parts)


def _node_text(node: Node) -> str:
    if node.type == "Patient":
        return _patient_summary(node)
    if node.type == "ExamResult":
        return _exam_result_summary(node)
    return escape(node.label)


def render_mermaid_markdown(graph: GraphBuilder) -> str:
    """Produz Markdown contendo o resumo e o fluxograma Mermaid."""
    lines = [
        f"# Grafo do caso {graph.case_id}",
        "",
        f"- Nós: {len(graph.nodes)}",
        f"- Arestas: {len(graph.edges)}",
        "",
        "```mermaid",
        _HORIZONTAL_LAYOUT,
        "flowchart LR",
    ]

    for node_type, (fill, stroke) in _NODE_STYLES.items():
        lines.append(
            f"  classDef {node_type} fill:{fill},stroke:{stroke},color:#111827"
        )

    lines.append("")
    for node in graph.nodes:
        label = _node_text(node)
        lines.append(f'  {node.node_id}["{label}"]:::{node.type}')

    lines.append("")
    for edge in graph.edges:
        relation = escape(edge.relation)
        lines.append(
            f"  {edge.source_id} -->|{relation}| {edge.target_id}"
        )

    lines.extend(["```", ""])
    return "\n".join(lines)
