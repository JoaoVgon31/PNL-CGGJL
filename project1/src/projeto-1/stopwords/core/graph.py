"""Construção incremental das tabelas de nós e arestas de um caso."""

import re
from collections import defaultdict
from typing import Any

from .models import Edge, NODE_PREFIXES, Node

_CASE_ID_PATTERN = re.compile(r"PMC\d+_\d{2}")


def _normalize_label(raw_label: str) -> str:
    return re.sub(r"\s+", " ", raw_label.strip())


class GraphBuilder:
    """Constrói e deduplica o grafo (nós + arestas) de um caso clínico."""

    def __init__(self, case_id: str) -> None:
        if _CASE_ID_PATTERN.fullmatch(case_id) is None:
            raise ValueError(f"invalid case_id: {case_id!r}")

        self.case_id = case_id
        self.nodes: list[Node] = []
        self.edges: list[Edge] = []

        self._node_counters: dict[str, int] = defaultdict(int)
        self._node_ids: set[str] = set()
        self._nodes_by_key: dict[tuple[str, str], Node] = {}

    def _next_node_id(self, node_type: str) -> str:
        self._node_counters[node_type] += 1
        return f"{NODE_PREFIXES[node_type]}{self._node_counters[node_type]}"

    def add_node(
        self,
        node_type: str,
        raw_label: str,
        attributes: dict[str, Any] | None = None,
    ) -> Node:
        if not raw_label or not raw_label.strip():
            raise ValueError("raw_label cannot be empty")

        label = _normalize_label(raw_label)
        key = (node_type, label)

        if key in self._nodes_by_key:
            existing = self._nodes_by_key[key]
            for attr_key, value in (attributes or {}).items():
                if value not in (None, "") and existing.attributes.get(attr_key) in (None, ""):
                    existing.attributes[attr_key] = value
            return existing

        node = Node(
            case_id=self.case_id,
            node_id=self._next_node_id(node_type),
            type=node_type,
            label=label,
            attributes=dict(attributes or {}),
        )
        self.nodes.append(node)
        self._node_ids.add(node.node_id)
        self._nodes_by_key[key] = node
        return node

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation: str,
        attributes: dict[str, Any] | None = None,
    ) -> Edge:
        if source_id not in self._node_ids:
            raise ValueError(f"source node does not exist: {source_id!r}")
        if target_id not in self._node_ids:
            raise ValueError(f"target node does not exist: {target_id!r}")

        edge = Edge(
            case_id=self.case_id,
            edge_id=f"e{len(self.edges) + 1}",
            source_id=source_id,
            target_id=target_id,
            relation=relation,
            attributes=dict(attributes or {}),
        )
        self.edges.append(edge)
        return edge

    def node_rows(self) -> list[dict[str, str]]:
        return [node.to_row() for node in self.nodes]

    def edge_rows(self) -> list[dict[str, str]]:
        return [edge.to_row() for edge in self.edges]
