"""Construção validada das tabelas de nós e arestas."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from models import Edge, NODE_PREFIXES, Node


class GraphBuilder:
    def __init__(self, case_id: str) -> None:
        self.case_id = case_id
        self.nodes: list[Node] = []
        self.edges: list[Edge] = []
        self._node_counts: dict[str, int] = defaultdict(int)
        self._edge_count = 0
        self._node_ids: set[str] = set()
        self._nodes_by_key: dict[tuple[str, str, tuple], Node] = {}
        self._edge_keys: set[tuple[str, str, str, int | None, int | None]] = set()

    @staticmethod
    def _identity_attributes(node_type: str, attributes: dict[str, Any]) -> tuple:
        identity_names = {
            "Patient": (),
            "Symptom": ("polarity",),
            "History": ("subject", "polarity", "category"),
            "Finding": ("polarity", "size"),
            "Exam": ("modality",),
            "ExamResult": ("value", "unit", "raw_text"),
            "Diagnosis": ("certainty", "polarity", "role"),
            "Medication": ("dose_value", "dose_unit", "frequency"),
            "Treatment": ("status",),
            "AnatomicalSite": ("laterality", "region_qualifier"),
            "Outcome": ("type", "timing", "polarity"),
            "Concept": ("vocabulary", "code"),
        }[node_type]
        return tuple(
            (name, str(attributes[name]))
            for name in identity_names
            if attributes.get(name) not in (None, "")
        )

    def add_node(
        self,
        node_type: str,
        label: str,
        attributes: dict[str, Any] | None = None,
        *,
        deduplicate: bool = True,
    ) -> Node:
        if node_type not in NODE_PREFIXES:
            raise ValueError(f"invalid node type: {node_type!r}")
        clean_label = " ".join(label.strip(" \t\n,;:().").split())
        node_attributes = dict(attributes or {})
        key = (
            node_type,
            clean_label.casefold(),
            self._identity_attributes(node_type, node_attributes),
        )
        if deduplicate and key in self._nodes_by_key:
            existing = self._nodes_by_key[key]
            for name, value in node_attributes.items():
                if existing.attributes.get(name) in (None, "") and value not in (None, ""):
                    existing.attributes[name] = value
            return existing

        self._node_counts[node_type] += 1
        node = Node(
            case_id=self.case_id,
            node_id=f"{NODE_PREFIXES[node_type]}{self._node_counts[node_type]}",
            type=node_type,
            label=clean_label,
            attributes=node_attributes,
        )
        self.nodes.append(node)
        self._node_ids.add(node.node_id)
        if deduplicate:
            self._nodes_by_key[key] = node
        return node

    def add_edge(
        self,
        source: Node,
        target: Node,
        relation: str,
        attributes: dict[str, Any] | None = None,
    ) -> Edge:
        if source.node_id not in self._node_ids or target.node_id not in self._node_ids:
            raise ValueError("both edge endpoints must already belong to the graph")
        edge_attributes = dict(attributes or {})
        key = (
            source.node_id,
            target.node_id,
            relation,
            edge_attributes.get("char_start"),
            edge_attributes.get("char_end"),
        )
        if key in self._edge_keys:
            return next(
                edge for edge in self.edges
                if (
                    edge.source_id,
                    edge.target_id,
                    edge.relation,
                    edge.attributes.get("char_start"),
                    edge.attributes.get("char_end"),
                ) == key
            )
        self._edge_count += 1
        edge = Edge(
            case_id=self.case_id,
            edge_id=f"e{self._edge_count}",
            source_id=source.node_id,
            target_id=target.node_id,
            relation=relation,
            attributes=edge_attributes,
        )
        self.edges.append(edge)
        self._edge_keys.add(key)
        return edge

    def node_rows(self) -> list[dict[str, str]]:
        return [node.to_row() for node in self.nodes]

    def edge_rows(self) -> list[dict[str, str]]:
        return [edge.to_row() for edge in self.edges]
