"""Limpeza de stop-words na string final de um label já extraído."""

import re


def clean_label(label: str, remove_words: frozenset[str], protect_words: frozenset[str]) -> str:
    """Remove tokens de remove_words (menos protect_words) do label. Nunca esvazia o label."""
    words_to_remove = remove_words - protect_words
    if not words_to_remove:
        return label

    tokens = label.split()
    kept = [
        token for token in tokens
        if re.sub(r"[^\w]", "", token).lower() not in words_to_remove
    ]
    cleaned = " ".join(kept)
    return cleaned if cleaned else label
