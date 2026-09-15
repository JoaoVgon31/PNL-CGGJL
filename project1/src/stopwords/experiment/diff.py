"""Compara duas execuções do pipeline sobre o mesmo caso, por conteúdo (não por node_id)."""

from dataclasses import dataclass

from ..core.graph import GraphBuilder
from ..core.models import Node

_POLARITY_TYPES = {"Symptom", "Finding", "History", "Diagnosis", "Outcome"}


@dataclass(frozen=True)
class CaseDiff:
    """Diferença entre um grafo baseline e uma variante, para o mesmo caso."""

    case_id: str
    nodes_lost: int
    nodes_gained: int
    polarity_changed: int
    edges_lost: int
    edges_gained: int
    polarity_changed_examples: tuple[str, ...]


def _node_key(node: Node) -> tuple[str, str]:
    return (node.type, node.label)


def _edge_key(edge, nodes_by_id: dict[str, Node]):
    source = nodes_by_id[edge.source_id]
    target = nodes_by_id[edge.target_id]
    return (edge.relation, _node_key(source), _node_key(target))


def diff_graphs(baseline: GraphBuilder, variant: GraphBuilder) -> CaseDiff:
    """Casa nós por (type, label) e arestas por (relation, origem, destino) — nunca por node_id."""
    baseline_by_key = {_node_key(node): node for node in baseline.nodes}
    variant_by_key = {_node_key(node): node for node in variant.nodes}

    baseline_keys = set(baseline_by_key)
    variant_keys = set(variant_by_key)

    nodes_lost = len(baseline_keys - variant_keys)
    nodes_gained = len(variant_keys - baseline_keys)

    polarity_changed = 0
    polarity_examples = []
    for key in baseline_keys & variant_keys:
        node_type, label = key
        if node_type not in _POLARITY_TYPES:
            continue
        baseline_polarity = baseline_by_key[key].attributes.get("polarity")
        variant_polarity = variant_by_key[key].attributes.get("polarity")
        if baseline_polarity != variant_polarity:
            polarity_changed += 1
            polarity_examples.append(f"{node_type}:{label} {baseline_polarity}->{variant_polarity}")

    baseline_nodes_by_id = {node.node_id: node for node in baseline.nodes}
    variant_nodes_by_id = {node.node_id: node for node in variant.nodes}

    baseline_edge_keys = {_edge_key(edge, baseline_nodes_by_id) for edge in baseline.edges}
    variant_edge_keys = {_edge_key(edge, variant_nodes_by_id) for edge in variant.edges}

    edges_lost = len(baseline_edge_keys - variant_edge_keys)
    edges_gained = len(variant_edge_keys - baseline_edge_keys)

    return CaseDiff(
        case_id=baseline.case_id,
        nodes_lost=nodes_lost,
        nodes_gained=nodes_gained,
        polarity_changed=polarity_changed,
        edges_lost=edges_lost,
        edges_gained=edges_gained,
        polarity_changed_examples=tuple(polarity_examples),
    )
