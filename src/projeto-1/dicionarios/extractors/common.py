from __future__ import annotations

import re
from dataclasses import dataclass

from core.graph import GraphBuilder
from core.models import Node

_GLOBAL_NEGATION = re.compile(r"^(?:no|without|denies?)\s+", re.IGNORECASE)
_LIST_SEPARATOR = re.compile(r"\s*(?:,|\band\b|\bor\b)\s*", re.IGNORECASE)
_ARTICLE_PREFIX = re.compile(r"^(?:a|an|the)\s+", re.IGNORECASE)


@dataclass(frozen=True)
class ExtractedEntity:
    node: Node
    evidence_text: str
    trigger: str
    char_start: int
    char_end: int


def find_sentence_end(text: str, start: int) -> int:
    match = re.search(r"[.!?\n]", text[start:])
    return len(text) if match is None else start + match.start()


def clean_entity_label(text: str) -> str:
    cleaned = text.strip(" \t,;:()")
    cleaned = _ARTICLE_PREFIX.sub("", cleaned)
    return cleaned.strip()


def split_list(text: str) -> list[str]:
    return [clean_entity_label(p) for p in _LIST_SEPARATOR.split(text) if clean_entity_label(p)]


def is_negated(scope: str) -> bool:
    return _GLOBAL_NEGATION.match(scope) is not None


def strip_negation(scope: str) -> str:
    return _GLOBAL_NEGATION.sub("", scope)


def record_evidence(
    graph: GraphBuilder,
    node: Node,
    case_text: str,
    trigger_start: int,
    trigger_label: str,
    scope_end: int,
) -> ExtractedEntity:
    evidence_text = case_text[trigger_start:scope_end].strip()
    return ExtractedEntity(
        node=node,
        evidence_text=evidence_text,
        trigger=trigger_label,
        char_start=trigger_start,
        char_end=scope_end,
    )
