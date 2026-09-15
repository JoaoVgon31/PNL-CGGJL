"""Extração baseada em regras de diagnósticos clínicos."""

import re

from ..core.graph import GraphBuilder
from .common import ExtractedEntity


_DIAGNOSIS_TRIGGER = re.compile(
    r"\b(?P<trigger>"
    r"suggesting\s+(?:the\s+)?diagnosis\s+of|"
    r"suspected\s+diagnosis\s+of|"
    r"differential\s+diagnosis\s+(?:included|of)|"
    r"was\s+diagnosed\s+with|diagnosed\s+with|"
    r"a\s+diagnosis\s+of|diagnosis\s+of|"
    r"consistent\s+with|"
    r"excluded\s+(?:a\s+diagnosis\s+of)?"
    r")\b",
    re.I,
)
_DIAGNOSIS_STOP = re.compile(
    r"\b(?:after\s+having|based\s+on|and\s+(?:was|the\s+patient)|therefore|which)\b",
    re.I,
)
_DIAGNOSIS_LIST = re.compile(r"\s*(?:,|\band\b|\bor\b)\s*", re.I)


def _diagnosis_attributes(trigger: str, sentence: str) -> dict[str, str]:
    folded = trigger.casefold()

    if "suggest" in folded or "suspected" in folded:
        certainty = "suspected"
    elif "differential" in folded:
        certainty = "probable"
    elif "excluded" in folded:
        certainty = "excluded"
    else:
        certainty = "confirmed"

    if "differential" in folded:
        role = "differential"
    elif re.search(r"\bsecondary\b", sentence, re.I):
        role = "secondary"
    else:
        role = "principal"

    return {
        "certainty": certainty,
        "polarity": "absent" if certainty == "excluded" else "present",
        "role": role,
    }


def extract_diagnoses(
    case_text: str,
    graph: GraphBuilder,
) -> list[ExtractedEntity]:
    """Extrai diagnósticos ancorados por expressões explícitas."""
    if case_text != graph.case_text:
        raise ValueError("case_text and graph use different texts")

    extracted: list[ExtractedEntity] = []
    for match in _DIAGNOSIS_TRIGGER.finditer(case_text):
        sentence_end_match = re.search(r"[.!?\n]", case_text[match.end():])
        end = len(case_text) if sentence_end_match is None else match.end() + sentence_end_match.start()
        scope = case_text[match.end():end].strip(" \t,:;")
        stop = _DIAGNOSIS_STOP.search(scope)
        if stop is not None:
            scope = scope[:stop.start()].strip(" \t,;")
        if not scope:
            continue

        # Parênteses de figura/citação não pertencem ao rótulo.
        scope = re.sub(r"\s*\((?:Fig(?:ure)?|Table)\s*\d+[^)]*\)\s*$", "", scope, flags=re.I)
        labels = [
            re.sub(r"^(?:a|an|the)\s+", "", part.strip(" \t,;:"), flags=re.I)
            for part in _DIAGNOSIS_LIST.split(scope)
        ]
        trigger = match.group("trigger")
        attributes = _diagnosis_attributes(trigger, case_text[match.start():end])

        for label in (label for label in labels if label):
            node = graph.add_node("Diagnosis", label, attributes)
            extracted.append(
                ExtractedEntity(
                    node=node,
                    evidence_text=case_text[match.start():end].strip(),
                    trigger=trigger,
                    char_start=match.start(),
                    char_end=end,
                )
            )

    return extracted
