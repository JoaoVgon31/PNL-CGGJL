"""Estruturas e utilitários compartilhados pelos extratores de entidade."""

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Sentence:
    """Uma sentença do case_text, com seus offsets no texto original."""

    text: str
    start: int
    end: int
    index: int


def split_sentences(text: str) -> list[Sentence]:
    """Quebra o texto em sentenças por pontuação terminal, preservando offsets.

    Trata . como terminador apenas quando não seguido por dígito (para decimais como 3.5).
    """
    sentences = []
    start = 0
    index = 0
    for match in re.finditer(r"(?:\.(?!\d)|[!?\n])+", text):
        end = match.start()
        if end > start:
            sentences.append(Sentence(text=text[start:end], start=start, end=end, index=index))
            index += 1
        start = match.end()
    if start < len(text):
        sentences.append(Sentence(text=text[start:], start=start, end=len(text), index=index))
    return sentences


@dataclass(frozen=True)
class Mention:
    """Uma entidade extraída, com a evidência textual que a sustenta."""

    node_type: str
    label: str
    attributes: dict[str, Any]
    sentence: Sentence
    trigger: str
    char_start: int
    char_end: int
    hedged: bool


_NEGATION_TRIGGERS = (
    "ruled out", "no evidence of", "negative for", "unremarkable for",
    "free of", "denies", "denied", "deny", "without", "no", "not",
)

_HEDGE_SUSPECTED_TRIGGERS = ("suggestive of", "suggesting", "possible")
_HEDGE_PROBABLE_TRIGGERS = ("consistent with", "probable", "presumed", "likely")

# Compile regex patterns with word boundaries to avoid false positives (e.g., "cannot" matching "not")
_NEGATION_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(t) for t in sorted(_NEGATION_TRIGGERS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

_HEDGE_SUSPECTED_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(t) for t in sorted(_HEDGE_SUSPECTED_TRIGGERS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)

_HEDGE_PROBABLE_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(t) for t in sorted(_HEDGE_PROBABLE_TRIGGERS, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def detect_polarity(sentence_text: str) -> str:
    """'absent' se a sentença contém um gatilho de negação, senão 'present'."""
    return "absent" if _NEGATION_PATTERN.search(sentence_text) else "present"


def detect_certainty(sentence_text: str) -> str:
    """'suspected'/'probable'/'confirmed' conforme o hedge mais forte encontrado."""
    if _HEDGE_SUSPECTED_PATTERN.search(sentence_text):
        return "suspected"
    if _HEDGE_PROBABLE_PATTERN.search(sentence_text):
        return "probable"
    return "confirmed"


def is_hedged(sentence_text: str) -> bool:
    return detect_certainty(sentence_text) != "confirmed"
