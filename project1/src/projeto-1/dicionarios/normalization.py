from __future__ import annotations

import unicodedata
from collections.abc import Callable

import nltk

_STRIP_CHARS = ".,;:()[]{}\"'`"


def normalize_token(token: str) -> str:
    token = unicodedata.normalize("NFKC", token)
    token = token.strip(_STRIP_CHARS)
    return token.lower()


def normalize_tokens(tokens: list[str]) -> list[str]:
    return [t for t in (normalize_token(tok) for tok in tokens) if t]


def align_normalized_tokens(
    tokens: list[str],
    normalize_fn: Callable[[str], str] = normalize_token,
) -> list[tuple[int, str]]:
    aligned = []
    for index, token in enumerate(tokens):
        normalized = normalize_fn(token)
        if normalized:
            aligned.append((index, normalized))
    return aligned


def normalize_term(
    text: str,
    normalize_fn: Callable[[str], str] = normalize_token,
) -> str:
    tokens = nltk.word_tokenize(text)
    return " ".join(t for t in (normalize_fn(tok) for tok in tokens) if t)


def build_normalized_gazetteer(
    raw_gazetteer: dict[str, list[tuple[str, str]]],
    normalize_fn: Callable[[str], str] = normalize_token,
) -> dict[str, list[tuple[str, str]]]:
    normalized: dict[str, list[tuple[str, str]]] = {}

    for raw_key, entries in raw_gazetteer.items():
        key = normalize_term(raw_key, normalize_fn)
        if not key:
            continue
        bucket = normalized.setdefault(key, [])
        for entry in entries:
            if entry not in bucket:
                bucket.append(entry)

    return normalized
