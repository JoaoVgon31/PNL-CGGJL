"""Normalização de valores numéricos e unidades clínicas."""

import re
import unicodedata
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


_NUMBER_PATTERN = re.compile(
    r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
)

_MEASUREMENT_PATTERN = re.compile(
    rf"""
    ^\s*
    (?P<value>{_NUMBER_PATTERN.pattern})
    \s*
    (?P<unit>.*?)    
    \s*$
    """,
    re.VERBOSE,
)

_RANGE_PREFIX = re.compile(
    r"^\s*(?:normal\s+range|reference\s+range)\s*[:,]?\s*",
    re.IGNORECASE,
)

_CLOSED_RANGE_PATTERN = re.compile(
    rf"""
    ^\s*
    (?P<low>{_NUMBER_PATTERN.pattern})
    \s*
    (?P<low_unit>%?)
    \s*
    (?:-|–|—|\bto\b)
    \s*
    (?P<high>{_NUMBER_PATTERN.pattern})
    \s*
    (?P<high_unit>.*?)
    \s*$
    """,
    re.VERBOSE | re.IGNORECASE,
)

_OPEN_RANGE_PATTERN = re.compile(
    rf"""
    ^\s*
    (?P<operator><=|>=|<|>)
    \s*
    (?P<value>{_NUMBER_PATTERN.pattern})
    \s*
    (?P<unit>.*?)
    \s*$
    """,
    re.VERBOSE,
)

_UNIT_VARIANTS = {
    "ng/ml": "ng/mL",
    "ng per milliliter": "ng/mL",
    "nanograms per milliliter": "ng/mL",
    "u/l": "U/L",
    "units/l": "U/L",
    "units per liter": "U/L",
    "iu/ml": "IU/mL",
    "iu/l": "IU/L",
    "mg/dl": "mg/dL",
    "mg/l": "mg/L",
    "g/dl": "g/dL",
    "mmol/l": "mmol/L",
    "mm/h": "mm/h",
    "%": "%",
    "per microliter": "/µL",
    "cells per microliter": "/µL",
    "/microliter": "/µL",
    "/μl": "/µL",
    "/ul": "/µL",
    "/mm3": "/µL",
    "cells/mm3": "/µL",
    "au/ml": "AU/mL",
}


@dataclass(frozen=True)
class Measurement:
    """Uma medição normalizada, preservando seu texto original."""

    value: Decimal
    unit: str | None
    raw_text: str

@dataclass(frozen=True)
class ReferenceRange:
    """Faixa de referência normalizada."""

    low: Decimal | None
    high: Decimal | None
    unit: str | None
    raw_text: str


def normalize_number(raw_value: str) -> Decimal:
    """Converte a forma textual de um número para Decimal."""
    if not isinstance(raw_value, str):
        raise TypeError("raw_value must be a string")

    value = raw_value.strip()

    if _NUMBER_PATTERN.fullmatch(value) is None:
        raise ValueError(f"invalid numeric value: {raw_value!r}")

    normalized = value.replace(",", "")

    try:
        return Decimal(normalized)
    except InvalidOperation as error:
        raise ValueError(
            f"invalid numeric value: {raw_value!r}"
        ) from error


def _unit_lookup_key(raw_unit: str) -> str:
    """Produz a forma usada para consultar o dicionário de unidades."""
    normalized = unicodedata.normalize("NFKC", raw_unit)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip().casefold()


def normalize_unit(raw_unit: str | None) -> str | None:
    """Converte uma variante de unidade para a forma canônica do projeto."""
    if raw_unit is None:
        return None

    if not isinstance(raw_unit, str):
        raise TypeError("raw_unit must be a string or None")

    if not raw_unit.strip():
        return None

    lookup_key = _unit_lookup_key(raw_unit)

    try:
        return _UNIT_VARIANTS[lookup_key]
    except KeyError as error:
        raise ValueError(
            f"unknown unit variant: {raw_unit!r}"
        ) from error


def parse_measurement(raw_text: str) -> Measurement:
    """Separa e normaliza o valor e a unidade de uma medição."""
    if not isinstance(raw_text, str):
        raise TypeError("raw_text must be a string")

    match = _MEASUREMENT_PATTERN.fullmatch(raw_text)

    if match is None:
        raise ValueError(f"invalid measurement: {raw_text!r}")

    raw_value = match.group("value")
    raw_unit = match.group("unit") or None

    return Measurement(
        value=normalize_number(raw_value),
        unit=normalize_unit(raw_unit),
        raw_text=raw_text,
    )

def parse_reference_range(raw_text: str) -> ReferenceRange:
    """Interpreta uma faixa de referência fechada ou aberta."""
    if not isinstance(raw_text, str):
        raise TypeError("raw_text must be a string")

    range_text = _RANGE_PREFIX.sub("", raw_text)

    closed_match = _CLOSED_RANGE_PATTERN.fullmatch(range_text)

    if closed_match is not None:
        low_unit = normalize_unit(
            closed_match.group("low_unit") or None
        )
        high_unit = normalize_unit(
            closed_match.group("high_unit") or None
        )

        if (
            low_unit is not None
            and high_unit is not None
            and low_unit != high_unit
        ):
            raise ValueError(
                "reference range uses incompatible units: "
                f"{raw_text!r}"
            )

        return ReferenceRange(
            low=normalize_number(closed_match.group("low")),
            high=normalize_number(closed_match.group("high")),
            unit=high_unit or low_unit,
            raw_text=raw_text,
        )

    open_match = _OPEN_RANGE_PATTERN.fullmatch(range_text)

    if open_match is not None:
        operator = open_match.group("operator")
        value = normalize_number(open_match.group("value"))
        unit = normalize_unit(open_match.group("unit") or None)

        if operator in {"<", "<="}:
            low = None
            high = value
        else:
            low = value
            high = None

        return ReferenceRange(
            low=low,
            high=high,
            unit=unit,
            raw_text=raw_text,
        )

    raise ValueError(f"invalid reference range: {raw_text!r}")

def supported_unit_variants() -> tuple[str, ...]:
    """Retorna as grafias de unidades reconhecidas pelo normalizador."""
    return tuple(_UNIT_VARIANTS)