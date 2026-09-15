from __future__ import annotations

import re

from core.graph import GraphBuilder

from .common import ExtractedEntity

_MEDICATION = re.compile(
    r"\b(?P<drug>[A-Za-z][a-zA-Z\-]{3,})\s+"
    r"(?P<dose_value>\d+(?:\.\d+)?)\s?(?P<dose_unit>mg|g|mcg|IU|mL|units)\b"
    r"(?:\s+(?P<frequency>once daily|twice daily|three times daily|four times daily|as needed))?",
    re.IGNORECASE,
)
_STOPWORDS = {"level", "dose", "dosage", "range", "normal", "value"}


def extract_medications(case_text: str, graph: GraphBuilder) -> list[ExtractedEntity]:
    extracted: list[ExtractedEntity] = []

    for match in _MEDICATION.finditer(case_text):
        drug = match.group("drug")
        if drug.lower() in _STOPWORDS:
            continue

        node = graph.add_node(
            "Medication",
            drug,
            {
                "dose_value": match.group("dose_value"),
                "dose_unit": match.group("dose_unit"),
                "frequency": match.group("frequency"),
            },
        )
        extracted.append(
            ExtractedEntity(
                node=node,
                evidence_text=match.group(0),
                trigger="dose pattern",
                char_start=match.start(),
                char_end=match.end(),
            )
        )

    return extracted
