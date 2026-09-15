"""Estruturas e utilitários compartilhados pelos extratores."""

import re
from dataclasses import dataclass

from ..core.models import Node


@dataclass(frozen=True)
class ExtractedEntity:
    """Nó extraído acompanhado de sua evidência textual."""

    node: Node
    evidence_text: str
    trigger: str
    char_start: int
    char_end: int


def find_sentence_end(text: str, start: int) -> int:
    """Encontra o fim da sentença sem incluir sua pontuação."""
    match = re.search(r"[.!?\n]", text[start:])
    return len(text) if match is None else start + match.start()
