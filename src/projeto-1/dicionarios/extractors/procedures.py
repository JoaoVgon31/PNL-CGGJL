from __future__ import annotations

import re

from core.graph import GraphBuilder

from .common import ExtractedEntity, clean_entity_label, find_sentence_end, is_negated, strip_negation

_UNDERWENT = re.compile(r"\bunderwent\b", re.IGNORECASE)
_TREATED_WITH = re.compile(r"\b(?:was |were )?treated with\b", re.IGNORECASE)
_WAS_PLANNED = re.compile(r"\bwas planned\b", re.IGNORECASE)
_CONVERTED_TO = re.compile(r"\bconverted to\b", re.IGNORECASE)
_ABBREVIATION = re.compile(r"^\s*\((?P<abbr>[A-Z]{2,6})\)")

_SURGERY_KEYWORDS = (
    "resection", "surgery", "pancreatectomy", "cystgastrostomy", "transfusion",
    "drainage", "laparoscop", "transplant", "repair", "excision", "stapler",
)
_IMAGING_KEYWORDS = ("tomography", "ultrasound", "mri", "x-ray", "scan", "ultrasonography", "radiograph")
_LAB_KEYWORDS = ("antigen", "level", "count", "assay", "culture")
_ENDOSCOPY_KEYWORDS = ("endoscopy", "colonoscopy", "endoscopic", "sigmoidoscopy")
_PATHOLOGY_KEYWORDS = ("biopsy", "pathology", "histology", "fna", "aspiration")


def _classify(phrase: str) -> tuple[str, str | None]:
    lowered = phrase.lower()
    if any(k in lowered for k in _SURGERY_KEYWORDS):
        return "Treatment", None
    if any(k in lowered for k in _IMAGING_KEYWORDS):
        return "Exam", "imaging"
    if any(k in lowered for k in _LAB_KEYWORDS):
        return "Exam", "laboratory"
    if any(k in lowered for k in _ENDOSCOPY_KEYWORDS):
        return "Exam", "endoscopy"
    if any(k in lowered for k in _PATHOLOGY_KEYWORDS):
        return "Exam", "pathology"
    return "Exam", None


def _first_phrase(scope: str) -> str:
    return re.split(r"[.;]| and | with |,", scope, maxsplit=1)[0].strip()


def extract_exams_and_treatments(
    case_text: str, graph: GraphBuilder
) -> tuple[list[ExtractedEntity], list[ExtractedEntity]]:
    exams: list[ExtractedEntity] = []
    treatments: list[ExtractedEntity] = []

    for trigger_match in _UNDERWENT.finditer(case_text):
        scope_start = trigger_match.end()
        sentence_end = find_sentence_end(case_text, scope_start)
        scope = case_text[scope_start:sentence_end].strip()
        if not scope:
            continue

        phrase = clean_entity_label(_first_phrase(scope))
        if not phrase:
            continue

        node_type, modality = _classify(phrase)
        attributes: dict[str, str | None] = {}
        abbreviation = None

        if node_type == "Exam":
            after_phrase = scope[len(phrase):].lstrip(" ,")
            abbr_match = _ABBREVIATION.match(after_phrase)
            if abbr_match is not None:
                abbreviation = abbr_match.group("abbr")
            attributes = {"modality": modality, "abbreviation": abbreviation}
        else:
            attributes = {"type": "surgery", "status": "performed"}

        node = graph.add_node(node_type, phrase, attributes)
        entity = ExtractedEntity(
            node=node,
            evidence_text=case_text[trigger_match.start():sentence_end].strip(),
            trigger="underwent",
            char_start=trigger_match.start(),
            char_end=sentence_end,
        )
        (exams if node_type == "Exam" else treatments).append(entity)

    for trigger_match in _TREATED_WITH.finditer(case_text):
        scope_start = trigger_match.end()
        sentence_end = find_sentence_end(case_text, scope_start)
        scope = case_text[scope_start:sentence_end].strip()
        if not scope:
            continue

        polarity_scope = strip_negation(scope) if is_negated(scope) else scope
        for label in re.split(r",| and ", polarity_scope):
            label = clean_entity_label(label)
            if not label:
                continue
            node = graph.add_node("Treatment", label, {"type": "supportive", "status": "performed"})
            treatments.append(
                ExtractedEntity(
                    node=node,
                    evidence_text=case_text[trigger_match.start():sentence_end].strip(),
                    trigger="treated with",
                    char_start=trigger_match.start(),
                    char_end=sentence_end,
                )
            )

    for trigger_match in _WAS_PLANNED.finditer(case_text):
        sentence_start = case_text.rfind(".", 0, trigger_match.start()) + 1
        phrase = clean_entity_label(case_text[sentence_start:trigger_match.start()].strip())
        if not phrase:
            continue
        node = graph.add_node("Treatment", phrase, {"type": "surgery", "status": "planned"})
        treatments.append(
            ExtractedEntity(
                node=node,
                evidence_text=case_text[sentence_start:trigger_match.end()].strip(),
                trigger="was planned",
                char_start=sentence_start,
                char_end=trigger_match.end(),
            )
        )

    for trigger_match in _CONVERTED_TO.finditer(case_text):
        scope_start = trigger_match.end()
        sentence_end = find_sentence_end(case_text, scope_start)
        phrase = clean_entity_label(case_text[scope_start:sentence_end].strip())
        if not phrase:
            continue
        node = graph.add_node("Treatment", phrase, {"type": "surgery", "status": "converted"})
        treatments.append(
            ExtractedEntity(
                node=node,
                evidence_text=case_text[trigger_match.start():sentence_end].strip(),
                trigger="converted to",
                char_start=trigger_match.start(),
                char_end=sentence_end,
            )
        )

    return exams, treatments
