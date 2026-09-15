"""Tokenizadores baseados em espaços, Treebank e regras clínicas."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from models import Token


NUMBER_SOURCE = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"

UNIT_VARIANTS = (
    "cells/µL", "cells/uL", "beats/min", "mEq/L", "mmol/L", "mcg/mL",
    "ng/mL", "ng/dL", "pg/mL", "mg/dL", "mg/mL", "g/dL", "IU/mL",
    "U/mL", "U/L", "mm/h", "mmHg", "AU/mL", "/µL", "/uL", "/mm3",
    "kg/m2", "cm3", "mm3", "mL", "mcg", "µg", "ug", "mg", "kg",
    "cm", "mm", "cc", "IU", "mEq", "g", "L", "%",
)

_UNIT_SOURCE = "|".join(
    re.escape(unit) for unit in sorted(UNIT_VARIANTS, key=len, reverse=True)
)

_FIGURE_SOURCE = (
    r"\((?:fig(?:ure)?s?\.?)\s*\d+[a-z]?"
    r"(?:\s*[-–—]\s*\d+[a-z]?)?\)"
)

CLINICAL_TOKEN_RE = re.compile(
    rf"""
      (?P<FIGURE_REF>{_FIGURE_SOURCE})
    | (?P<NUM_HYPHEN_WORD>{NUMBER_SOURCE}(?:-[A-Za-z][A-Za-z0-9]*)+)
    | (?P<NUMBER_RANGE>{NUMBER_SOURCE}(?:[-–—]{NUMBER_SOURCE})+)
    | (?P<NUMBER>[+-]?{NUMBER_SOURCE})
    | (?P<UNIT>(?:{_UNIT_SOURCE}))(?![A-Za-z0-9_])
    | (?P<OPERATOR><=|>=|<|>)
    | (?P<WORD>[^\W\d_][\w]*(?:[-/][\w]+)*)
    | (?P<PUNCTUATION>[^\w\s])
    """,
    re.VERBOSE | re.IGNORECASE | re.UNICODE,
)

_NUMBER_RE = re.compile(rf"[+-]?{NUMBER_SOURCE}")
_NUMBER_RANGE_RE = re.compile(rf"{NUMBER_SOURCE}(?:[-–—]{NUMBER_SOURCE})+")
_NUM_HYPHEN_WORD_RE = re.compile(
    rf"{NUMBER_SOURCE}(?:-[A-Za-z][A-Za-z0-9]*)+",
    re.IGNORECASE,
)
_UNIT_RE = re.compile(rf"(?:{_UNIT_SOURCE})", re.IGNORECASE)
_FIGURE_RE = re.compile(_FIGURE_SOURCE, re.IGNORECASE)


def classify_surface(surface: str) -> str:
    """Classifica uma superfície produzida por um tokenizador genérico."""
    if _FIGURE_RE.fullmatch(surface):
        return "FIGURE_REF"
    if _NUM_HYPHEN_WORD_RE.fullmatch(surface):
        return "NUM_HYPHEN_WORD"
    if _NUMBER_RANGE_RE.fullmatch(surface):
        return "NUMBER_RANGE"
    if _NUMBER_RE.fullmatch(surface):
        return "NUMBER"
    if _UNIT_RE.fullmatch(surface):
        return "UNIT"
    if surface in {"<", ">", "<=", ">="}:
        return "OPERATOR"
    if all(not char.isalnum() for char in surface):
        return "PUNCTUATION"
    return "WORD"


class BaseTokenizer(ABC):
    name: str

    @abstractmethod
    def tokenize(self, text: str) -> list[Token]:
        raise NotImplementedError

    @staticmethod
    def _validate(text: str, tokens: list[Token]) -> None:
        previous_end = 0
        for expected_index, token in enumerate(tokens):
            token.validate_against(text)
            if token.index != expected_index:
                raise ValueError("token indices must be sequential")
            if token.start < previous_end:
                raise ValueError("tokens must not overlap")
            skipped = text[previous_end:token.start]
            if skipped and not skipped.isspace():
                raise ValueError(f"non-whitespace text was skipped: {skipped!r}")
            previous_end = token.end
        tail = text[previous_end:]
        if tail and not tail.isspace():
            raise ValueError(f"non-whitespace text was skipped: {tail!r}")


class WhitespaceTokenizer(BaseTokenizer):
    """Baseline ingênuo: cada sequência não branca é um token."""

    name = "whitespace"

    def tokenize(self, text: str) -> list[Token]:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        tokens = [
            Token(match.group(), match.start(), match.end(), index, "RAW")
            for index, match in enumerate(re.finditer(r"\S+", text))
        ]
        self._validate(text, tokens)
        return tokens


class TreebankTokenizer(BaseTokenizer):
    """Adaptador com offsets para ``nltk.tokenize.TreebankWordTokenizer``."""

    name = "treebank"

    def tokenize(self, text: str) -> list[Token]:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        try:
            from nltk.tokenize import TreebankWordTokenizer
        except ImportError as error:
            raise RuntimeError(
                "NLTK is required for the treebank tokenizer; "
                "install src/projeto-1/tokenizacao/requirements.txt"
            ) from error

        tokenizer = TreebankWordTokenizer()
        tokens = []
        for index, (start, end) in enumerate(tokenizer.span_tokenize(text)):
            surface = text[start:end]
            tokens.append(
                Token(surface, start, end, index, classify_surface(surface))
            )
        self._validate(text, tokens)
        return tokens


class ClinicalRegexTokenizer(BaseTokenizer):
    """Tokenizador regex que protege construções frequentes no MultiCaRe."""

    name = "clinical_regex"

    def tokenize(self, text: str) -> list[Token]:
        if not isinstance(text, str):
            raise TypeError("text must be a string")

        tokens: list[Token] = []
        previous_end = 0
        for match in CLINICAL_TOKEN_RE.finditer(text):
            skipped = text[previous_end:match.start()]
            if skipped and not skipped.isspace():
                raise ValueError(f"tokenizer skipped text: {skipped!r}")
            tokens.append(
                Token(
                    text=match.group(),
                    start=match.start(),
                    end=match.end(),
                    index=len(tokens),
                    kind=match.lastgroup or "UNKNOWN",
                )
            )
            previous_end = match.end()

        tail = text[previous_end:]
        if tail and not tail.isspace():
            raise ValueError(f"tokenizer skipped text: {tail!r}")
        self._validate(text, tokens)
        return tokens


TOKENIZERS = {
    "whitespace": WhitespaceTokenizer,
    "treebank": TreebankTokenizer,
    "clinical_regex": ClinicalRegexTokenizer,
}


def get_tokenizer(name: str) -> BaseTokenizer:
    try:
        return TOKENIZERS[name]()
    except KeyError as error:
        choices = ", ".join(TOKENIZERS)
        raise ValueError(f"unknown tokenizer {name!r}; choose one of: {choices}") from error
