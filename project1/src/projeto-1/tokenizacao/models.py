"""Estruturas de dados do pipeline de tokenização."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
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
}

_CASE_ID_RE = re.compile(r"PMC\d+_\d{2}")


@dataclass(frozen=True)
class Token:
    """Token ancorado no texto original por offsets semiabertos [start, end)."""

    text: str
    start: int
    end: int
    index: int
    kind: str

    def validate_against(self, source_text: str) -> None:
        if not (0 <= self.start < self.end <= len(source_text)):
            raise ValueError(f"invalid token span: {self.start}:{self.end}")
        if source_text[self.start:self.end] != self.text:
            raise ValueError(
                "token surface does not match source text: "
                f"{self.text!r} != {source_text[self.start:self.end]!r}"
            )


@dataclass(frozen=True)
class ClinicalCase:
    article_id: str
    age: Decimal | None
    case_id: str
    case_text: str
    gender: str

    def __post_init__(self) -> None:
        if _CASE_ID_RE.fullmatch(self.case_id) is None:
            raise ValueError(f"invalid case_id: {self.case_id!r}")


def _attribute_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def serialize_attributes(attributes: dict[str, Any]) -> str:
    return "; ".join(
        f"{key}={_attribute_value(value)}"
        for key, value in attributes.items()
        if value not in (None, "")
    )


@dataclass
class Node:
    case_id: str
    node_id: str
    type: str
    label: str
    attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if _CASE_ID_RE.fullmatch(self.case_id) is None:
            raise ValueError(f"invalid case_id: {self.case_id!r}")
        prefix = NODE_PREFIXES.get(self.type)
        if prefix is None:
            raise ValueError(f"invalid node type: {self.type!r}")
        if re.fullmatch(rf"{prefix}\d+", self.node_id) is None:
            raise ValueError(f"invalid node_id for {self.type}: {self.node_id!r}")
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
        if self.relation not in ALLOWED_RELATIONS:
            raise ValueError(f"invalid relation: {self.relation!r}")
        if re.fullmatch(r"e\d+", self.edge_id) is None:
            raise ValueError(f"invalid edge_id: {self.edge_id!r}")

    def to_row(self) -> dict[str, str]:
        return {
            "case_id": self.case_id,
            "edge_id": self.edge_id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation,
            "attributes": serialize_attributes(self.attributes),
        }
