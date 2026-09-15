from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from .models import NODE_PREFIXES, Edge, Node


@dataclass
class GraphBuilder:
    case_id: str
    case_text: str

    def __post_init__(self) -> None:
        self._node_counters: Counter[str] = Counter()
        self._edge_count = 0
        self.nodes: list[Node] = []
        self.edges: list[Edge] = []

    def add_node(self, type_: str, label: str, attributes: dict[str, Any] | None = None) -> Node:
        prefix = NODE_PREFIXES[type_]
        self._node_counters[type_] += 1
        node_id = f"{prefix}{self._node_counters[type_]}"
        node = Node(self.case_id, node_id, type_, label, attributes or {})
        self.nodes.append(node)
        return node

    def add_edge(
        self,
        source: Node | str,
        target: Node | str,
        relation: str,
        attributes: dict[str, Any] | None = None,
    ) -> Edge:
        self._edge_count += 1
        edge_id = f"e{self._edge_count}"
        source_id = source.node_id if isinstance(source, Node) else source
        target_id = target.node_id if isinstance(target, Node) else target
        edge = Edge(self.case_id, edge_id, source_id, target_id, relation, attributes or {})
        self.edges.append(edge)
        return edge

    def node_rows(self) -> list[dict[str, str]]:
        return [n.to_row() for n in self.nodes]

    def edge_rows(self) -> list[dict[str, str]]:
        return [e.to_row() for e in self.edges]
