"""Extração dos antecedentes clínicos e familiares."""

import re

from ..core.graph import GraphBuilder
from .common import ExtractedEntity, find_sentence_end
from .symptoms import split_list


_HISTORY_TRIGGER = re.compile(
    r"""\b(?P<trigger>
        family\s+history\s+(?:significant\s+for|of)
        |past\s+medical\s+history\s+(?:significant\s+for|of)
        |medical\s+history\s+(?:significant\s+for|of)
        |surgical\s+history\s+(?:significant\s+for|of)
        |medication\s+history\s+(?:significant\s+for|of)
    )\b""",
    re.VERBOSE | re.IGNORECASE,
)
_HISTORY_SCOPE_STOP = re.compile(
    r"\b(?:who\s+presented|presented\s+with|was\s+admitted)\b", re.IGNORECASE
)
_SURGERY_TERMS = re.compile(
    r"\b(?:surgery|replacement|resection|repair|transplantation|\w+ectomy)\b",
    re.IGNORECASE,
)
_EXPOSURE_TERMS = re.compile(
    r"\b(?:smoking|tobacco|alcohol|radiation|exposure)\b", re.IGNORECASE
)


def _history_category(raw_label: str, trigger: str) -> str:
    trigger_folded = trigger.casefold()
    if "medication history" in trigger_folded:
        return "medication"
    if "surgical history" in trigger_folded or _SURGERY_TERMS.search(raw_label):
        return "surgery"
    if _EXPOSURE_TERMS.search(raw_label):
        return "exposure"
    return "condition"


def extract_history(case_text: str, graph: GraphBuilder) -> list[ExtractedEntity]:
    """Extrai antecedentes introduzidos por gatilhos explícitos."""
    if case_text != graph.case_text:
        raise ValueError("case_text and graph use different texts")

    extracted: list[ExtractedEntity] = []
    for trigger_match in _HISTORY_TRIGGER.finditer(case_text):
        scope_start = trigger_match.end()
        sentence_end = find_sentence_end(case_text, scope_start)
        scope = case_text[scope_start:sentence_end].strip()
        stop_match = _HISTORY_SCOPE_STOP.search(scope)
        if stop_match is not None:
            scope = scope[:stop_match.start()].strip(" \t,;")
        if not scope:
            continue

        trigger = trigger_match.group("trigger")
        subject = "family" if trigger.casefold().startswith("family") else "patient"
        relation_degree = "unspecified" if subject == "family" else None
        evidence_end = scope_start + len(case_text[scope_start:sentence_end])
        if stop_match is not None:
            evidence_end = scope_start + stop_match.start()
        evidence_text = case_text[trigger_match.start():evidence_end].strip()

        for raw_label in (label for label in split_list(scope) if label):
            node = graph.add_node(
                "History",
                raw_label,
                {
                    "subject": subject,
                    "polarity": "present",
                    "relation_degree": relation_degree,
                    "category": _history_category(raw_label, trigger),
                },
            )
            extracted.append(
                ExtractedEntity(
                    node=node,
                    evidence_text=evidence_text,
                    trigger=trigger,
                    char_start=trigger_match.start(),
                    char_end=evidence_end,
                )
            )
    return extracted
