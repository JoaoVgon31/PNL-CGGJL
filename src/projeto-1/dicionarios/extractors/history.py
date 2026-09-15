from __future__ import annotations

import re

from core.graph import GraphBuilder

from .common import ExtractedEntity, find_sentence_end, is_negated, split_list, strip_negation

_TRIGGER = re.compile(
    r"\b(?P<trigger>past medical history|family history|medical history)"
    r"(?:\s+(?:significant for|of))?\s+",
    re.IGNORECASE,
)


def extract_history(case_text: str, graph: GraphBuilder) -> list[ExtractedEntity]:
    extracted: list[ExtractedEntity] = []
    subject_default = "patient"

    for trigger_match in _TRIGGER.finditer(case_text):
        subject = "family" if "family" in trigger_match.group("trigger").lower() else subject_default
        scope_start = trigger_match.end()
        sentence_end = find_sentence_end(case_text, scope_start)
        scope = case_text[scope_start:sentence_end].strip()
        if not scope:
            continue

        polarity = "absent" if is_negated(scope) else "present"
        scope = strip_negation(scope)
        labels = split_list(scope)

        for label in labels:
            node = graph.add_node(
                "History",
                label,
                {"subject": subject, "polarity": polarity},
            )
            extracted.append(
                ExtractedEntity(
                    node=node,
                    evidence_text=case_text[trigger_match.start():sentence_end].strip(),
                    trigger=trigger_match.group("trigger"),
                    char_start=trigger_match.start(),
                    char_end=sentence_end,
                )
            )

    return extracted
