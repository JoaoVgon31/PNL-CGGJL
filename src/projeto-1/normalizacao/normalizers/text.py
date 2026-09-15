"""Funções para normalizar rótulos extraídos de casos clínicos."""

import re
import unicodedata


_WHITESPACE_PATTERN = re.compile(r"\s+")

# Pontuação removida somente quando aparece nas extremidades.
# O hífen não está aqui porque pode fazer parte de termos como "C-reactive".
_BOUNDARY_PUNCTUATION = " \t\n\r.,;:!?\"'`()[]{}"

# Algumas expressões clínicas perdem informação ou legibilidade quando o
# case folding é aplicado sem uma etapa posterior de restauração.
#
# Os limites (?<!\w) e (?!\w) impedem substituições dentro de outras palavras.
_CANONICAL_CASE_PATTERNS = (
    (
        re.compile(r"(?<!\w)ca\s*19\s*[-‐‑‒–—]\s*9(?!\w)", re.IGNORECASE),
        "CA 19-9",
    ),
    (
        re.compile(r"(?<!\w)her\s*[- ]?\s*2(?!\w)", re.IGNORECASE),
        "HER2",
    ),
    (
        re.compile(r"(?<!\w)ph(?!\w)", re.IGNORECASE),
        "pH",
    ),
    (
        re.compile(r"(?<!\w)igg(?!\w)", re.IGNORECASE),
        "IgG",
    ),
    (
        re.compile(r"(?<!\w)igm(?!\w)", re.IGNORECASE),
        "IgM",
    ),
    (
        re.compile(r"(?<!\w)iga(?!\w)", re.IGNORECASE),
        "IgA",
    ),
)


def normalize_unicode(text: str) -> str:
    """Padroniza representações Unicode equivalentes."""
    return unicodedata.normalize("NFKC", text)


def normalize_whitespace(text: str) -> str:
    """Substitui sequências de espaços por um único espaço."""
    return _WHITESPACE_PATTERN.sub(" ", text).strip()


def strip_boundary_punctuation(text: str) -> str:
    """Remove pontuação apenas do começo e do fim do texto."""
    return text.strip(_BOUNDARY_PUNCTUATION)

def restore_canonical_case(text: str) -> str:
    """Restaura a capitalização convencional de termos clínicos conhecidos."""
    restored = text

    for pattern, canonical_form in _CANONICAL_CASE_PATTERNS:
        restored = pattern.sub(canonical_form, restored)

    return restored

def normalize_label(text: str) -> str:
    """Produz a forma normalizada básica de um rótulo clínico."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    normalized = normalize_unicode(text)
    normalized = normalize_whitespace(normalized)
    normalized = strip_boundary_punctuation(normalized)
    normalized = normalized.casefold()
    normalized = restore_canonical_case(normalized)
    normalized = normalize_whitespace(normalized)

    return normalized