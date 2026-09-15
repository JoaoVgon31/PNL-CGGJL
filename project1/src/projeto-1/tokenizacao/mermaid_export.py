"""Visualização Mermaid do grafo completo e de um recorte para apresentação."""

from __future__ import annotations

from html import escape

from models import Edge, Node
from pipeline import PipelineResult


CLASS_BY_TYPE = {
    "Patient": "patient",
    "History": "history",
    "Symptom": "symptom",
    "Finding": "finding",
    "Exam": "exam",
    "ExamResult": "result",
    "Diagnosis": "diagnosis",
    "Treatment": "treatment",
    "Medication": "medication",
    "AnatomicalSite": "site",
    "Outcome": "outcome",
    "Concept": "concept",
}


def _display_label(node: Node) -> str:
    label = escape(node.label, quote=True)
    details: list[str] = []
    if node.type == "Patient":
        age = node.attributes.get("age")
        gender = node.attributes.get("gender")
        if age is not None:
            details.append(f"age={escape(str(age))}")
        if gender:
            details.append(f"gender={escape(str(gender))}")
    elif node.type == "ExamResult":
        value = node.attributes.get("value")
        unit = node.attributes.get("unit")
        if value is not None:
            details.append(f"value={escape(str(value))}")
        if unit:
            details.append(f"unit={escape(str(unit))}")
    elif node.type in {"Diagnosis", "Finding"}:
        for key in ("certainty", "polarity", "size"):
            value = node.attributes.get(key)
            if value:
                details.append(f"{key}={escape(str(value))}")

    lines = [f"<b>{escape(node.type)}</b>", label]
    if details:
        lines.append(" · ".join(details))
    return "<br/>".join(lines)


def _node_line(node: Node) -> str:
    css_class = CLASS_BY_TYPE[node.type]
    return f'    {node.node_id}["{_display_label(node)}"]:::{css_class}'


def _edge_line(edge: Edge) -> str:
    return (
        f"    {edge.source_id} -- \"{escape(edge.relation)}\" --> "
        f"{edge.target_id}"
    )


def _class_definitions() -> list[str]:
    return [
        "    classDef patient fill:#FFBD55,stroke:#1D6D7C,color:#333333,stroke-width:2px",
        "    classDef history fill:#E9EDF0,stroke:#777777,color:#333333",
        "    classDef symptom fill:#FFF0D2,stroke:#FFBD55,color:#333333",
        "    classDef finding fill:#D9F1F4,stroke:#39B8D3,color:#333333",
        "    classDef exam fill:#8CCAD3,stroke:#1D6D7C,color:#173E45,stroke-width:2px",
        "    classDef result fill:#39B8D3,stroke:#1D6D7C,color:#FFFFFF,stroke-width:2px",
        "    classDef diagnosis fill:#1D6D7C,stroke:#8664FF,color:#FFFFFF,stroke-width:2px",
        "    classDef treatment fill:#FFF0D2,stroke:#FFBD55,color:#333333",
        "    classDef medication fill:#FFF0D2,stroke:#FFBD55,color:#333333",
        "    classDef site fill:#E9EDF0,stroke:#8CCAD3,color:#333333",
        "    classDef outcome fill:#E9E2FF,stroke:#8664FF,color:#333333",
        "    classDef concept fill:#FFFFFF,stroke:#777777,color:#333333,stroke-dasharray:4 3",
        "    linkStyle default stroke:#8664FF,stroke-width:1.5px,color:#1D6D7C",
    ]


def _render(nodes: list[Node], edges: list[Edge], direction: str = "LR") -> str:
    lines = [
        '%%{init: {"theme": "base", "themeVariables": '
        '{"background": "transparent", "fontFamily": "Arial"}}}%%',
        f"flowchart {direction}",
    ]
    lines.extend(_node_line(node) for node in nodes)
    lines.append("")
    lines.extend(_edge_line(edge) for edge in edges)
    lines.append("")
    lines.extend(_class_definitions())
    return "\n".join(lines)


def render_full_graph(result: PipelineResult) -> str:
    """Documento Mermaid com todos os nós e arestas extraídos."""
    diagram = _render(result.graph.nodes, result.graph.edges, "LR")
    return (
        f"# Grafo completo — {result.case.case_id}\n\n"
        "Gerado automaticamente a partir das tabelas de nós e arestas.\n\n"
        f"```mermaid\n{diagram}\n```\n"
    )


def _slide_node_ids(result: PipelineResult) -> set[str]:
    """Seleciona o caminho Patient → Exam → ExamResult → diagnóstico presente."""
    graph = result.graph
    selected = {node.node_id for node in graph.nodes if node.type == "Patient"}
    result_ids = {node.node_id for node in graph.nodes if node.type == "ExamResult"}
    selected.update(result_ids)

    for edge in graph.edges:
        if edge.relation == "HAS_RESULT" and edge.target_id in result_ids:
            selected.add(edge.source_id)

    present_diagnoses = {
        node.node_id for node in graph.nodes
        if node.type == "Diagnosis" and node.attributes.get("polarity") != "absent"
    }
    for edge in graph.edges:
        if edge.relation == "SUPPORTS" and edge.source_id in result_ids and edge.target_id in present_diagnoses:
            selected.add(edge.target_id)
    return selected


def render_slide_graph(result: PipelineResult) -> str:
    """Recorte sem título, pronto para exportar como SVG transparente."""
    selected = _slide_node_ids(result)
    nodes = [node for node in result.graph.nodes if node.node_id in selected]
    allowed_relations = {"UNDERWENT_EXAM", "HAS_RESULT", "SUPPORTS", "DIAGNOSED_WITH"}
    edges = [
        edge for edge in result.graph.edges
        if edge.source_id in selected
        and edge.target_id in selected
        and edge.relation in allowed_relations
    ]
    return f"```mermaid\n{_render(nodes, edges, 'LR')}\n```\n"
