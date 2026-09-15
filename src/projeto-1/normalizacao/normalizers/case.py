"""Camada de normalização configurada para um caso clínico específico."""

from .acronyms import discover_acronyms, expand_acronyms
from .text import normalize_label
from .units import (
    Measurement,
    ReferenceRange,
    parse_measurement,
    parse_reference_range,
)


class CaseNormalizer:
    """Normaliza entidades e medições usando o contexto de um caso."""

    def __init__(self, case_text: str) -> None:
        if not isinstance(case_text, str):
            raise TypeError("case_text must be a string")

        self._case_text = case_text
        self._acronym_definitions = discover_acronyms(case_text)

    @property
    def acronym_definitions(self) -> dict[str, str]:
        """Retorna uma cópia das siglas descobertas no caso."""
        return dict(self._acronym_definitions)

    def normalize_entity_label(self, raw_label: str) -> str:
        """Expande siglas e normaliza o rótulo de uma entidade."""
        expanded_label = expand_acronyms(
            raw_label,
            self._acronym_definitions,
        )
        return normalize_label(expanded_label)

    def normalize_measurement(self, raw_text: str) -> Measurement:
        """Normaliza uma medição simples."""
        return parse_measurement(raw_text)

    def normalize_reference_range(
        self,
        raw_text: str,
    ) -> ReferenceRange:
        """Normaliza uma faixa de referência."""
        return parse_reference_range(raw_text)
