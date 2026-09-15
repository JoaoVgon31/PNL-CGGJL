"""Extração de sintomas do relato clínico."""

import re

from ..core.graph import GraphBuilder
from .common import ExtractedEntity, find_sentence_end


_SYMPTOM_TRIGGER = re.compile(
    r"""\b(?P<trigger>
        presented\s+with|complained\s+of|admitted\s+with|reported
    )\b""",
    re.VERBOSE | re.IGNORECASE,
)
_DURATION_PREFIX = re.compile(
    r"""^(?:an?\s+)?(?P<value>
        \d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten
    )[- ](?P<unit>day|week|month|year)s?\s+history\s+of\s+""",
    re.VERBOSE | re.IGNORECASE,
)
_ASSOCIATION_SEPARATOR = re.compile(
    r"\b(?:associated\s+with|accompanied\s+by)\b", re.IGNORECASE
)
_LIST_SEPARATOR = re.compile(r"\s*(?:,|\band\b|\bor\b)\s*", re.IGNORECASE)
_GLOBAL_NEGATION = re.compile(r"^(?:no|without)\s+", re.IGNORECASE)
_ATOMIC_SYMPTOMS = {
    "fever", "cough", "nausea", "constipation", "diarrhea", "vomiting",
    "emesis", "fatigue", "headache", "dyspnea", "weight loss",
    "night sweating", "abdominal distention",
}


def clean_entity_label(text: str) -> str:
    """Remove conectores superficiais de uma menção."""
    cleaned = text.strip(" \t,;:()")
    cleaned = re.sub(r"^(?:a|an|the)\s+", "", cleaned, flags=re.IGNORECASE)
    return _GLOBAL_NEGATION.sub("", cleaned).strip()


def split_list(text: str) -> list[str]:
    """Divide uma enumeração usando os mesmos limites dos sintomas."""
    return [clean_entity_label(part) for part in _LIST_SEPARATOR.split(text)]


def _is_atomic_symptom_list(text: str) -> bool:
    parts = [part.casefold() for part in split_list(text) if part]
    return len(parts) > 1 and all(part in _ATOMIC_SYMPTOMS for part in parts)


def _split_symptom_scope(scope: str) -> tuple[list[str], int]:
    association = _ASSOCIATION_SEPARATOR.search(scope)
    if association is not None:
        main_parts = [clean_entity_label(scope[:association.start()])]
        associated_parts = split_list(scope[association.end():])
        parts = main_parts + associated_parts
        return [part for part in parts if part], len(main_parts)
    if _GLOBAL_NEGATION.match(scope) or _is_atomic_symptom_list(scope):
        parts = [part for part in split_list(scope) if part]
        return parts, len(parts)
    return [clean_entity_label(scope)], 1


def _normalized_duration(match: re.Match[str]) -> str:
    value = match.group("value").casefold()
    unit = match.group("unit").casefold()
    suffix = "" if value in {"1", "one"} else "s"
    return f"{value} {unit}{suffix}"


def extract_symptoms(case_text: str, graph: GraphBuilder) -> list[ExtractedEntity]:
    """Extrai sintomas introduzidos por gatilhos explícitos."""
    if case_text != graph.case_text:
        raise ValueError("case_text and graph use different texts")

    extracted: list[ExtractedEntity] = []
    for trigger_match in _SYMPTOM_TRIGGER.finditer(case_text):
        scope_start = trigger_match.end()
        sentence_end = find_sentence_end(case_text, scope_start)
        scope = case_text[scope_start:sentence_end].strip()
        evidence_start = trigger_match.start()
        evidence_text = case_text[evidence_start:sentence_end].strip()
        if not scope:
            continue

        global_polarity = "absent" if _GLOBAL_NEGATION.match(scope) else "present"
        duration = None
        duration_match = _DURATION_PREFIX.match(scope)
        if duration_match is not None:
            duration = _normalized_duration(duration_match)
            scope = scope[duration_match.end():]

        symptom_labels, main_count = _split_symptom_scope(scope)
        for index, raw_label in enumerate(symptom_labels):
            node = graph.add_node(
                "Symptom",
                raw_label,
                {
                    "polarity": global_polarity,
                    "duration": duration if duration is not None and index < main_count else None,
                },
            )
            extracted.append(
                ExtractedEntity(
                    node=node,
                    evidence_text=evidence_text,
                    trigger=trigger_match.group("trigger"),
                    char_start=evidence_start,
                    char_end=sentence_end,
                )
            )
    return extracted
