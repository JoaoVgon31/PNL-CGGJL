"""Mascaramento de tokens de stop-words preservando comprimento/offsets."""

import re


def mask_text(text: str, remove_words: frozenset[str], protect_words: frozenset[str]) -> str:
    """Substitui tokens de remove_words (menos protect_words) por espaços do mesmo tamanho."""
    words_to_mask = remove_words - protect_words
    if not words_to_mask:
        return text

    pattern = re.compile(
        r"\b(" + "|".join(re.escape(word) for word in sorted(words_to_mask, key=len, reverse=True)) + r")\b",
        re.IGNORECASE,
    )

    def _blank(match: re.Match[str]) -> str:
        return " " * len(match.group(0))

    return pattern.sub(_blank, text)
