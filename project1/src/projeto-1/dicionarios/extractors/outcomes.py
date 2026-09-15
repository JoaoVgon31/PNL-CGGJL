from __future__ import annotations

import re

from core.graph import GraphBuilder

from .common import ExtractedEntity, find_sentence_end

_TRIGGERS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bdischarged\b", re.IGNORECASE), "discharge"),
    (re.compile(r"\bexpired\b|\bdied\b", re.IGNORECASE), "death"),
    (re.compile(r"\bresolution of\b", re.IGNORECASE), "resolution"),
    (re.compile(r"\bevidence of recurrence\b", re.IGNORECASE), "recurrence"),
]
_NEGATION_LOOKBEHIND = re.compile(r"\b(?:no|without)\s*$", re.IGNORECASE)


def extract_outcomes(case_text: str, graph: GraphBuilder) -> list[ExtractedEntity]:
    extracted: list[ExtractedEntity] = []

    for trigger_re, outcome_type in _TRIGGERS:
        for trigger_match in trigger_re.finditer(case_text):
            sentence_end = find_sentence_end(case_text, trigger_match.end())
            sentence_start = case_text.rfind(".", 0, trigger_match.start()) + 1
            scope = case_text[sentence_start:sentence_end].strip()

            preceding = case_text[max(0, trigger_match.start() - 15) : trigger_match.start()]
            polarity = "absent" if _NEGATION_LOOKBEHIND.search(preceding) else "present"
            label = trigger_match.group(0)

            node = graph.add_node(
                "Outcome",
                label,
                {"type": outcome_type, "polarity": polarity},
            )
            extracted.append(
                ExtractedEntity(
                    node=node,
                    evidence_text=scope,
                    trigger=trigger_match.group(0),
                    char_start=sentence_start,
                    char_end=sentence_end,
                )
            )

    return extracted
