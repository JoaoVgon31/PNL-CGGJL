from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

NODE_PREFIXES = {
    "Patient": "P",
    "History": "H",
    "Symptom": "S",
    "Finding": "F",
    "Exam": "E",
    "ExamResult": "R",
    "Diagnosis": "D",
    "Treatment": "T",
    "Medication": "M",
    "AnatomicalSite": "A",
    "Outcome": "O",
    "Concept": "C",
}

ALLOWED_RELATIONS = {
    "HAS_SYMPTOM",
    "HAS_HISTORY",
    "UNDERWENT_EXAM",
    "HAS_RESULT",
    "REVEALS",
    "HAS_FINDING",
    "SUPPORTS",
    "DIAGNOSED_WITH",
    "TREATED_WITH",
    "LOCATED_IN",
    "HAS_OUTCOME",
    "REVISES",
    "SAME_AS",
}

_CASE_ID_PATTERN = re.compile(r"PMC\d+_\d{2}")
_EDGE_ID_PATTERN = re.compile(r"e\d+")


def serialize_attributes(attributes: dict[str, Any]) -> str:
    parts = []
    for key, value in attributes.items():
        if value is None or value == "":
            continue
        parts.append(f"{key}={value}")
    return "; ".join(parts)


@dataclass
class Node:
    case_id: str
    node_id: str
    type: str
    label: str
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if _CASE_ID_PATTERN.fullmatch(self.case_id) is None:
            raise ValueError(f"invalid case_id: {self.case_id!r}")
        if self.type not in NODE_PREFIXES:
            raise ValueError(f"invalid node type: {self.type!r}")
        expected_prefix = NODE_PREFIXES[self.type]
        if re.fullmatch(rf"{expected_prefix}\d+", self.node_id) is None:
            raise ValueError(
                f"node_id {self.node_id!r} does not match type {self.type!r}"
            )
        if not self.label.strip():
            raise ValueError("node label cannot be empty")

    def to_row(self) -> dict[str, str]:
        return {
            "case_id": self.case_id,
            "node_id": self.node_id,
            "type": self.type,
            "label": self.label,
            "attributes": serialize_attributes(self.attributes),
        }


@dataclass
class Edge:
    case_id: str
    edge_id: str
    source_id: str
    target_id: str
    relation: str
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if _CASE_ID_PATTERN.fullmatch(self.case_id) is None:
            raise ValueError(f"invalid case_id: {self.case_id!r}")
        if _EDGE_ID_PATTERN.fullmatch(self.edge_id) is None:
            raise ValueError(f"invalid edge_id: {self.edge_id!r}")
        if not self.source_id or not self.target_id:
            raise ValueError("edge endpoints cannot be empty")
        if self.relation not in ALLOWED_RELATIONS:
            raise ValueError(f"invalid relation: {self.relation!r}")

    def to_row(self) -> dict[str, str]:
        return {
            "case_id": self.case_id,
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation,
            "attributes": serialize_attributes(self.attributes),
        }
