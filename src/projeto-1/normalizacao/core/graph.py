"""Construção incremental das tabelas de nós e arestas."""

import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from ..normalizers.case import CaseNormalizer
from .models import Edge, NODE_PREFIXES, Node


_CASE_ID_PATTERN = re.compile(r"PMC\d+_\d{2}")

# Atributos que distinguem entidades com o mesmo rótulo.
_IDENTITY_ATTRIBUTES = {
    "Patient": (),
    "History": (
        "subject",
        "polarity",
        "relation_degree",
        "category",
    ),
    "Symptom": ("polarity",),
    "Finding": ("polarity", "certainty"),
    "Exam": ("modality", "timing", "contrast"),
    "ExamResult": (
        "value",
        "unit",
        "reference_range_low",
        "reference_range_high",
    ),
    "Diagnosis": ("certainty", "polarity", "role"),
    "Treatment": ("status", "converted_to", "timing"),
    "Medication": (
        "dose_value",
        "dose_unit",
        "frequency",
        "route",
        "dose_change",
        "timing",
    ),
    "AnatomicalSite": (
        "laterality",
        "region_qualifier",
    ),
    "Outcome": ("type", "timing", "polarity"),
    "Concept": ("vocabulary", "code"),
}


@dataclass(frozen=True)
class NormalizationImpact:
    """Comparação das entidades antes e depois da normalização."""

    mentions_processed: int
    raw_nodes: int
    normalized_nodes: int
    labels_changed: int
    nodes_merged: int

    def to_dict(self) -> dict[str, int]:
        return {
            "mentions_processed": self.mentions_processed,
            "raw_nodes": self.raw_nodes,
            "normalized_nodes": self.normalized_nodes,
            "labels_changed": self.labels_changed,
            "nodes_merged": self.nodes_merged,
        }


class GraphBuilder:
    """Constrói e deduplica o grafo de um caso clínico."""

    def __init__(self, case_id: str, case_text: str) -> None:
        if _CASE_ID_PATTERN.fullmatch(case_id) is None:
            raise ValueError(f"invalid case_id: {case_id!r}")

        self.case_id = case_id
        self.case_text = case_text
        self.normalizer = CaseNormalizer(case_text)

        self.nodes: list[Node] = []
        self.edges: list[Edge] = []

        self._node_counters: dict[str, int] = defaultdict(int)
        self._edge_counter = 0
        self._node_ids: set[str] = set()

        self._nodes_by_label: dict[
            tuple[str, str],
            list[Node],
        ] = defaultdict(list)
        self._raw_node_keys: set[tuple[Any, ...]] = set()
        self._mentions_processed = 0
        self._labels_changed = 0

    def _next_node_id(self, node_type: str) -> str:
        if node_type not in NODE_PREFIXES:
            raise ValueError(f"invalid node type: {node_type!r}")

        self._node_counters[node_type] += 1
        prefix = NODE_PREFIXES[node_type]

        return f"{prefix}{self._node_counters[node_type]}"

    def _normalize_node_label(
        self,
        node_type: str,
        raw_label: str,
    ) -> str:
        if not isinstance(raw_label, str):
            raise TypeError("raw_label must be a string")

        if node_type == "Patient":
            return raw_label.strip()

        return self.normalizer.normalize_entity_label(raw_label)

    def _identity_key(
        self,
        node_type: str,
        label: str,
        attributes: dict[str, Any],
    ) -> tuple[Any, ...]:
        attribute_names = _IDENTITY_ATTRIBUTES[node_type]

        identity_values = tuple(
            (
                attribute_name,
                str(attributes[attribute_name]),
            )
            for attribute_name in attribute_names
            if attributes.get(attribute_name) not in (None, "")
        )

        return node_type, label, identity_values

    def _identity_attributes_are_compatible(
        self,
        existing: Node,
        new_attributes: dict[str, Any],
    ) -> bool:
        """Aceita atributos ausentes, mas rejeita valores conflitantes."""
        attribute_names = _IDENTITY_ATTRIBUTES[existing.type]

        for attribute_name in attribute_names:
            existing_value = existing.attributes.get(attribute_name)
            new_value = new_attributes.get(attribute_name)

            existing_is_filled = existing_value not in (None, "")
            new_is_filled = new_value not in (None, "")

            if (
                existing_is_filled
                and new_is_filled
                and str(existing_value) != str(new_value)
            ):
                return False

        return True

    @staticmethod
    def _merge_missing_attributes(
        existing: Node,
        new_attributes: dict[str, Any],
    ) -> None:
        """Preenche atributos ausentes sem sobrescrever conflitos."""
        for key, value in new_attributes.items():
            if value in (None, ""):
                continue

            if existing.attributes.get(key) in (None, ""):
                existing.attributes[key] = value

    def add_node(
        self,
        node_type: str,
        raw_label: str,
        attributes: dict[str, Any] | None = None,
        *,
        deduplicate: bool = True,
    ) -> Node:
        """Normaliza e adiciona ou reutiliza um nó."""
        if node_type not in NODE_PREFIXES:
            raise ValueError(f"invalid node type: {node_type!r}")

        if not isinstance(raw_label, str):
            raise TypeError("raw_label must be a string")

        node_attributes = dict(attributes or {})
        cleaned_raw_label = raw_label.strip()
        normalized_label = self._normalize_node_label(
            node_type,
            raw_label,
        )

        self._mentions_processed += 1

        if cleaned_raw_label != normalized_label:
            self._labels_changed += 1

        raw_key = self._identity_key(
            node_type,
            cleaned_raw_label,
            node_attributes,
        )

        if deduplicate:
            self._raw_node_keys.add(raw_key)

            label_key = (node_type, normalized_label)
            existing_nodes = self._nodes_by_label.get(
                label_key,
                [],
            )

            for existing in existing_nodes:
                if self._identity_attributes_are_compatible(
                    existing,
                    node_attributes,
                ):
                    self._merge_missing_attributes(
                        existing,
                        node_attributes,
                    )
                    return existing
        else:
            self._raw_node_keys.add(
                raw_key + ("mention", self._mentions_processed)
            )

        node = Node(
            case_id=self.case_id,
            node_id=self._next_node_id(node_type),
            type=node_type,
            label=normalized_label,
            attributes=node_attributes,
        )

        self.nodes.append(node)
        self._node_ids.add(node.node_id)

        if deduplicate:
            label_key = (node_type, normalized_label)
            self._nodes_by_label[label_key].append(node)

        return node

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation: str,
        attributes: dict[str, Any] | None = None,
    ) -> Edge:
        if source_id not in self._node_ids:
            raise ValueError(
                f"source node does not exist: {source_id!r}"
            )

        if target_id not in self._node_ids:
            raise ValueError(
                f"target node does not exist: {target_id!r}"
            )

        self._edge_counter += 1

        edge = Edge(
            case_id=self.case_id,
            edge_id=f"e{self._edge_counter}",
            source_id=source_id,
            target_id=target_id,
            relation=relation,
            attributes=dict(attributes or {}),
        )

        self.edges.append(edge)
        return edge

    def normalization_impact(self) -> NormalizationImpact:
        raw_nodes = len(self._raw_node_keys)
        normalized_nodes = len(self.nodes)

        return NormalizationImpact(
            mentions_processed=self._mentions_processed,
            raw_nodes=raw_nodes,
            normalized_nodes=normalized_nodes,
            labels_changed=self._labels_changed,
            nodes_merged=max(0, raw_nodes - normalized_nodes),
        )

    def node_rows(self) -> list[dict[str, str]]:
        return [node.to_row() for node in self.nodes]

    def edge_rows(self) -> list[dict[str, str]]:
        return [edge.to_row() for edge in self.edges]
