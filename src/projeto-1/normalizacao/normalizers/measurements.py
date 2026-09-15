"""Localização de medições em textos clínicos."""

import re
from dataclasses import dataclass

from .units import (
    Measurement,
    ReferenceRange,
    parse_measurement,
    parse_reference_range,
    supported_unit_variants,
)


_NUMBER_SOURCE = (
    r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
)


def _unit_variant_pattern(variant: str) -> str:
    """Converte uma variante literal em uma expressão regular."""
    pattern = re.escape(variant)
    pattern = pattern.replace(r"\ ", r"\s+")

    # O texto pode usar tanto mu grego quanto o sinal de micro.
    pattern = pattern.replace("μ", "[μµ]")

    # O expoente pode aparecer como caractere sobrescrito.
    pattern = pattern.replace("3", "[3³]")

    return pattern


_UNIT_SOURCE = "|".join(
    _unit_variant_pattern(variant)
    for variant in sorted(
        supported_unit_variants(),
        key=len,
        reverse=True,
    )
)

_MEASUREMENT_IN_TEXT = re.compile(
    rf"""
    (?<![\w.,])
    (?P<measurement>
        {_NUMBER_SOURCE}
        \s*
        (?:{_UNIT_SOURCE})
    )
    (?![A-Za-z0-9])
    """,
    re.VERBOSE | re.IGNORECASE,
)

_RANGE_PREFIX_SOURCE = (
    r"(?:normal\s+range|reference\s+range)\s*[:,]?\s*"
)

_CLOSED_RANGE_IN_TEXT = re.compile(
    rf"""
    (?<![\w.,])
    (?P<reference_range>
        (?:{_RANGE_PREFIX_SOURCE})?
        {_NUMBER_SOURCE}
        \s*%?
        \s*(?:-|–|—|\bto\b)\s*
        {_NUMBER_SOURCE}
        \s*(?:{_UNIT_SOURCE})?
    )
    (?![A-Za-z0-9])
    """,
    re.VERBOSE | re.IGNORECASE,
)

_OPEN_RANGE_IN_TEXT = re.compile(
    rf"""
    (?<![\w.,])
    (?P<reference_range>
        (?:{_RANGE_PREFIX_SOURCE})?
        (?:<=|>=|<|>)
        \s*
        {_NUMBER_SOURCE}
        \s*(?:{_UNIT_SOURCE})?
    )
    (?![A-Za-z0-9])
    """,
    re.VERBOSE | re.IGNORECASE,
)

_EXPLICIT_RANGE_PREFIX = re.compile(
    rf"^\s*{_RANGE_PREFIX_SOURCE}",
    re.IGNORECASE,
)

_RANGE_BEFORE = re.compile(
    rf"""
    {_NUMBER_SOURCE}
    \s*%?
    \s*[-–—]\s*$
    """,
    re.VERBOSE,
)

_RANGE_AFTER = re.compile(
    rf"""
    ^\s*[-–—]\s*
    {_NUMBER_SOURCE}
    \s*(?:{_UNIT_SOURCE})
    """,
    re.VERBOSE | re.IGNORECASE,
)

_OPEN_RANGE_BEFORE = re.compile(r"(?:<=|>=|<|>)\s*$")

_VALUE_BEFORE_MINUS = re.compile(
    rf"""
    {_NUMBER_SOURCE}
    \s*%?
    \s*$
    """,
    re.VERBOSE,
)


@dataclass(frozen=True)
class ExtractedMeasurement:
    """Medição localizada no texto original."""

    measurement: Measurement
    char_start: int
    char_end: int

@dataclass(frozen=True)
class ExtractedReferenceRange:
    """Faixa de referência localizada no texto original."""

    reference_range: ReferenceRange
    char_start: int
    char_end: int


def _belongs_to_reference_range(
    text: str,
    start: int,
    end: int,
) -> bool:
    """Verifica se a medição é um dos limites de uma faixa."""
    preceding_text = text[max(0, start - 60):start]
    following_text = text[end:min(len(text), end + 60)]

    minus_is_range_separator = (
        text[start:start + 1] == "-"
        and _VALUE_BEFORE_MINUS.search(preceding_text) is not None
    )

    return any(
        (
            _RANGE_BEFORE.search(preceding_text),
            _RANGE_AFTER.search(following_text),
            _OPEN_RANGE_BEFORE.search(preceding_text),
            minus_is_range_separator,
        )
    )


def find_measurements(text: str) -> list[ExtractedMeasurement]:
    """Localiza medições que não pertencem a faixas de referência."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    extracted: list[ExtractedMeasurement] = []

    for match in _MEASUREMENT_IN_TEXT.finditer(text):
        start, end = match.span("measurement")

        if _belongs_to_reference_range(text, start, end):
            continue

        raw_text = match.group("measurement")

        extracted.append(
            ExtractedMeasurement(
                measurement=parse_measurement(raw_text),
                char_start=start,
                char_end=end,
            )
        )

    return extracted

def find_reference_ranges(
    text: str,
) -> list[ExtractedReferenceRange]:
    """Localiza faixas de referência explícitas no texto."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    extracted: list[ExtractedReferenceRange] = []

    patterns = (
        _CLOSED_RANGE_IN_TEXT,
        _OPEN_RANGE_IN_TEXT,
    )

    for pattern in patterns:
        for match in pattern.finditer(text):
            raw_text = match.group("reference_range")
            reference_range = parse_reference_range(raw_text)

            # Uma faixa sem unidade, como "10-20", é ambígua e pode ser
            # idade, data ou duração. Só a aceitamos quando o texto declara
            # que se trata de uma faixa de referência.
            if (
                reference_range.unit is None
                and _EXPLICIT_RANGE_PREFIX.match(raw_text) is None
            ):
                continue

            start, end = match.span("reference_range")

            extracted.append(
                ExtractedReferenceRange(
                    reference_range=reference_range,
                    char_start=start,
                    char_end=end,
                )
            )

    return sorted(
        extracted,
        key=lambda result: result.char_start,
    )
