"""Construção de resultados laboratoriais a partir de medições e faixas."""

import re
from dataclasses import dataclass

from ..normalizers.measurements import (
    ExtractedMeasurement,
    ExtractedReferenceRange,
    find_measurements,
    find_reference_ranges,
)


# Um ponto entre dois dígitos é decimal; os demais pontos encerram sentença.
_SENTENCE_BOUNDARY = re.compile(r"\.(?!\d)|[!?]|\n+")

_INTERPRETATION_PATTERNS = {
    "elevated": re.compile(
        r"\b(?:elevated|increased|high)\b",
        re.IGNORECASE,
    ),
    "decreased": re.compile(
        r"\b(?:decreased|reduced|low)\b",
        re.IGNORECASE,
    ),
    "abnormal": re.compile(
        r"\babnormal\b",
        re.IGNORECASE,
    ),
    "positive": re.compile(
        r"\bpositive\b",
        re.IGNORECASE,
    ),
    "negative": re.compile(
        r"\bnegative\b",
        re.IGNORECASE,
    ),
    # O lookahead impede que "normal range" seja interpretado como
    # uma afirmação de que o resultado medido é normal.
    "normal": re.compile(
        r"\bnormal\b(?!\s+(?:reference\s+)?range\b)",
        re.IGNORECASE,
    ),
}


@dataclass(frozen=True)
class LabResultCandidate:
    """Resultado quantitativo encontrado em uma sentença."""

    measurement: ExtractedMeasurement
    reference_range: ExtractedReferenceRange | None
    interpretation: str | None
    interpretation_source: str | None
    evidence_text: str
    char_start: int
    char_end: int


def _sentence_span(
    text: str,
    position: int,
) -> tuple[int, int]:
    """Encontra os offsets da sentença que contém uma posição."""
    start = 0
    end = len(text)

    for boundary in _SENTENCE_BOUNDARY.finditer(text):
        if boundary.end() <= position:
            start = boundary.end()
            continue

        if boundary.start() >= position:
            end = boundary.end()
            break

    while start < end and text[start].isspace():
        start += 1

    while end > start and text[end - 1].isspace():
        end -= 1

    return start, end


def _range_distance(
    measurement: ExtractedMeasurement,
    reference_range: ExtractedReferenceRange,
) -> int:
    """Calcula a distância textual entre uma medição e uma faixa."""
    if reference_range.char_start >= measurement.char_end:
        return reference_range.char_start - measurement.char_end

    if measurement.char_start >= reference_range.char_end:
        return measurement.char_start - reference_range.char_end

    return 0


def _units_are_compatible(
    measurement: ExtractedMeasurement,
    reference_range: ExtractedReferenceRange,
) -> bool:
    """Verifica se medição e faixa podem representar a mesma grandeza."""
    measurement_unit = measurement.measurement.unit
    range_unit = reference_range.reference_range.unit

    return (
        measurement_unit is None
        or range_unit is None
        or measurement_unit == range_unit
    )


def _nearest_compatible_range(
    measurement: ExtractedMeasurement,
    ranges: list[ExtractedReferenceRange],
    sentence_start: int,
    sentence_end: int,
) -> ExtractedReferenceRange | None:
    """Seleciona a faixa compatível mais próxima na mesma sentença."""
    candidates = [
        reference_range
        for reference_range in ranges
        if reference_range.char_start >= sentence_start
        and reference_range.char_end <= sentence_end
        and _units_are_compatible(measurement, reference_range)
    ]

    if not candidates:
        return None

    return min(
        candidates,
        key=lambda reference_range: _range_distance(
            measurement,
            reference_range,
        ),
    )

def _span_distance(
    first_start: int,
    first_end: int,
    second_start: int,
    second_end: int,
) -> int:
    """Calcula a distância entre dois intervalos de caracteres."""
    if first_end <= second_start:
        return second_start - first_end

    if second_end <= first_start:
        return first_start - second_end

    return 0


def _find_stated_interpretation(
    sentence: str,
    measurement_start: int,
    measurement_end: int,
) -> str | None:
    """Encontra a interpretação declarada mais próxima da medição."""
    candidates: list[tuple[int, str]] = []

    for interpretation, pattern in _INTERPRETATION_PATTERNS.items():
        for match in pattern.finditer(sentence):
            distance = _span_distance(
                match.start(),
                match.end(),
                measurement_start,
                measurement_end,
            )
            candidates.append((distance, interpretation))

    if not candidates:
        return None

    return min(candidates, key=lambda candidate: candidate[0])[1]


def _derive_interpretation(
    measurement: ExtractedMeasurement,
    reference_range: ExtractedReferenceRange,
) -> str:
    """Compara o valor medido com os limites da faixa."""
    value = measurement.measurement.value
    low = reference_range.reference_range.low
    high = reference_range.reference_range.high

    if low is not None and value < low:
        return "decreased"

    if high is not None and value > high:
        return "elevated"

    return "normal"

def find_lab_result_candidates(
    text: str,
) -> list[LabResultCandidate]:
    """Reúne medições e faixas encontradas na mesma sentença."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    measurements = find_measurements(text)
    ranges = find_reference_ranges(text)
    results: list[LabResultCandidate] = []

    for measurement in measurements:
        sentence_start, sentence_end = _sentence_span(
            text,
            measurement.char_start,
        )

        reference_range = _nearest_compatible_range(
            measurement,
            ranges,
            sentence_start,
            sentence_end,
        )

        sentence = text[sentence_start:sentence_end]

        relative_measurement_start = (
            measurement.char_start - sentence_start
        )
        relative_measurement_end = (
            measurement.char_end - sentence_start
        )

        interpretation = _find_stated_interpretation(
            sentence,
            relative_measurement_start,
            relative_measurement_end,
        )

        if interpretation is not None:
            interpretation_source = "stated"
        elif reference_range is not None:
            interpretation = _derive_interpretation(
                measurement,
                reference_range,
            )
            interpretation_source = "derived"
        else:
            interpretation_source = None

        results.append(
            LabResultCandidate(
                measurement=measurement,
                reference_range=reference_range,
                interpretation=interpretation,
                interpretation_source=interpretation_source,
                evidence_text=sentence,
                char_start=sentence_start,
                char_end=sentence_end,
            )
        )

    return results
