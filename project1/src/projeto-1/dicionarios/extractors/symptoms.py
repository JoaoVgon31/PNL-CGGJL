from __future__ import annotations

import re

from core.graph import GraphBuilder

from .common import ExtractedEntity, find_sentence_end, is_negated, split_list, strip_negation

_TRIGGER = re.compile(
    r"\b(?P<trigger>presented with|complained of|admitted with|reported)\b",
    re.IGNORECASE,
)
_DURATION_PREFIX = re.compile(
    r"^(?:an?\s+)?(?P<value>\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten)"
    r"[- ](?P<unit>day|week|month|year)s?\s+history\s+of\s+",
    re.IGNORECASE,
)
_ASSOCIATION = re.compile(r"\b(?:associated with|accompanied by)\b", re.IGNORECASE)


def _normalized_duration(match: re.Match[str]) -> str:
    value = match.group("value").lower()
    unit = match.group("unit").lower()
    suffix = "" if value in {"1", "one"} else "s"
    return f"{value} {unit}{suffix}"


def extract_symptoms(case_text: str, graph: GraphBuilder) -> list[ExtractedEntity]:
    extracted: list[ExtractedEntity] = []

    for trigger_match in _TRIGGER.finditer(case_text):
        scope_start = trigger_match.end()
        sentence_end = find_sentence_end(case_text, scope_start)
        scope = case_text[scope_start:sentence_end].strip()
        if not scope:
            continue

        polarity = "absent" if is_negated(scope) else "present"
        scope = strip_negation(scope)

        duration = None
        duration_match = _DURATION_PREFIX.match(scope)
        if duration_match is not None:
            duration = _normalized_duration(duration_match)
            scope = scope[duration_match.end():]

        association = _ASSOCIATION.search(scope)
        if association is not None:
            main_parts = split_list(scope[: association.start()])
            associated_parts = split_list(scope[association.end():])
            labels = main_parts + associated_parts
            main_count = len(main_parts)
        else:
            labels = split_list(scope) if "," in scope or " and " in scope.lower() else [scope.strip(" .")]
            main_count = len(labels)

        for index, label in enumerate(labels):
            if not label:
                continue
            node = graph.add_node(
                "Symptom",
                label,
                {
                    "polarity": polarity,
                    "duration": duration if duration is not None and index < main_count else None,
                },
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
