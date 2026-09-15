from __future__ import annotations

import re

from core.graph import GraphBuilder

from .common import ExtractedEntity, clean_entity_label, find_sentence_end, is_negated, strip_negation

_TRIGGERS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bsuggesting the diagnosis of\b", re.IGNORECASE), "suspected"),
    (re.compile(r"\ba diagnosis of\b", re.IGNORECASE), "confirmed"),
    (re.compile(r"\bdiagnosed with\b", re.IGNORECASE), "confirmed"),
    (re.compile(r"\bconsistent with\b", re.IGNORECASE), "confirmed"),
    (re.compile(r"\bsuspected\b", re.IGNORECASE), "suspected"),
]


def extract_diagnoses(case_text: str, graph: GraphBuilder) -> list[ExtractedEntity]:
    extracted: list[ExtractedEntity] = []

    for trigger_re, certainty in _TRIGGERS:
        for trigger_match in trigger_re.finditer(case_text):
            scope_start = trigger_match.end()
            sentence_end = find_sentence_end(case_text, scope_start)
            scope = case_text[scope_start:sentence_end].strip()
            if not scope:
                continue

            polarity = "absent" if is_negated(scope) else "present"
            scope = strip_negation(scope)
            label = clean_entity_label(scope.split(",")[0].strip(" ."))
            if not label:
                continue

            node = graph.add_node(
                "Diagnosis",
                label,
                {"certainty": certainty, "polarity": polarity, "role": "principal"},
            )
            extracted.append(
                ExtractedEntity(
                    node=node,
                    evidence_text=case_text[trigger_match.start():sentence_end].strip(),
                    trigger=trigger_match.group(0),
                    char_start=trigger_match.start(),
                    char_end=sentence_end,
                )
            )

    return extracted
