"""Extração baseada em regras de medicamentos e tratamentos."""

import re
from decimal import Decimal

from ..core.graph import GraphBuilder
from .common import ExtractedEntity


_MEDICATION = re.compile(
    r"\b(?P<label>[A-Za-z][A-Za-z-]*(?:\s+[A-Za-z][A-Za-z-]*){0,2})"
    r"\s*\(?\s*(?P<dose>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>mg|g|mcg|IU|mL|units)\b",
    re.I,
)
_MEDICATION_PREFIX = re.compile(
    r"^.*\b(?:with|and|of|to|received|administered|reduced|increased)\s+",
    re.I,
)
_ROUTE_PREFIX = re.compile(
    r"^(?:oral|intravenous|intramuscular|subcutaneous|topical|inhaled)\s+",
    re.I,
)
_FREQUENCY = re.compile(
    r"\b(once daily|twice daily|three times daily|four times daily|as needed)\b",
    re.I,
)
_ROUTES = {
    "intravenous": re.compile(r"\b(?:intravenous|IV)\b", re.I),
    "intramuscular": re.compile(r"\b(?:intramuscular|IM)\b", re.I),
    "subcutaneous": re.compile(r"\bsubcutaneous\b", re.I),
    "oral": re.compile(r"\b(?:oral|orally|by mouth)\b", re.I),
    "topical": re.compile(r"\btopical\b", re.I),
    "inhaled": re.compile(r"\binhaled\b", re.I),
}
_TREATMENTS = (
    (re.compile(r"\blaparoscopic distal pancreatectomy\b", re.I), "laparoscopic distal pancreatectomy", "surgery"),
    (re.compile(r"\bopen resection\b", re.I), "open resection", "surgery"),
    (re.compile(r"\b(?:EUS[- ]guided )?cystgastrostomy\b", re.I), "EUS-guided cystgastrostomy", "procedure"),
    (re.compile(r"\bgastrojejunostomy\b", re.I), "gastrojejunostomy", "surgery"),
    (re.compile(r"\bblood transfusion\b|\btransfused\b", re.I), "blood transfusion", "transfusion"),
    (re.compile(r"\bintravenous fluids\b", re.I), "intravenous fluids", "supportive"),
    (re.compile(r"\banalgesia\b", re.I), "analgesia", "supportive"),
    (re.compile(r"\bchemotherapy\b", re.I), "chemotherapy", "procedure"),
    (re.compile(r"\bradiotherapy\b", re.I), "radiotherapy", "radiotherapy"),
    (re.compile(r"\b(?:abscess |pseudocyst )?drainage\b", re.I), "drainage", "procedure"),
)
_TREATMENT_CONTEXT = re.compile(
    r"\b(?:treated|underwent|received|started|performed|planned|converted|transfused|drained)\b",
    re.I,
)


def _sentence_bounds(text: str, position: int) -> tuple[int, int]:
    start = max(text.rfind(mark, 0, position) for mark in ".!?\n") + 1
    endings = [index for mark in ".!?\n" if (index := text.find(mark, position)) >= 0]
    end = min(endings) if endings else len(text)
    return start, end


def _route(sentence: str) -> str | None:
    for canonical, pattern in _ROUTES.items():
        if pattern.search(sentence):
            return canonical
    return None


def extract_medications(case_text: str, graph: GraphBuilder) -> list[ExtractedEntity]:
    """Extrai fármacos acompanhados de dose explícita."""
    if case_text != graph.case_text:
        raise ValueError("case_text and graph use different texts")

    extracted: list[ExtractedEntity] = []
    for match in _MEDICATION.finditer(case_text):
        start, end = _sentence_bounds(case_text, match.start())
        sentence = case_text[start:end].strip()
        raw_label = _MEDICATION_PREFIX.sub("", match.group("label")).strip()
        raw_label = _ROUTE_PREFIX.sub("", raw_label).strip()
        following = case_text[match.end():min(end, match.end() + 60)]
        preceding = case_text[max(start, match.start() - 50):match.start()]
        change_context = case_text[start:match.end()]
        frequency_match = _FREQUENCY.search(following)

        if re.search(r"\breduc(?:ed|tion)|\blowered\b", change_context, re.I):
            dose_change = "reduced"
        elif re.search(r"\bincreas(?:ed|ing)\b", change_context, re.I):
            dose_change = "increased"
        else:
            dose_change = "initial"

        node = graph.add_node(
            "Medication",
            raw_label,
            {
                "dose_value": Decimal(match.group("dose")),
                "dose_unit": match.group("unit"),
                "frequency": frequency_match.group(1).casefold() if frequency_match else None,
                "route": _route(sentence),
                "dose_change": dose_change,
            },
        )
        extracted.append(
            ExtractedEntity(node, sentence, match.group(0), start, end)
        )

    return extracted


def extract_treatments(case_text: str, graph: GraphBuilder) -> list[ExtractedEntity]:
    """Extrai intervenções não farmacológicas em contextos de tratamento."""
    if case_text != graph.case_text:
        raise ValueError("case_text and graph use different texts")

    extracted: list[ExtractedEntity] = []
    for pattern, label, treatment_type in _TREATMENTS:
        for match in pattern.finditer(case_text):
            start, end = _sentence_bounds(case_text, match.start())
            sentence = case_text[start:end].strip()
            if _TREATMENT_CONTEXT.search(sentence) is None:
                continue

            if re.search(r"\bplanned\b", sentence, re.I):
                status = "planned"
            elif re.search(r"\bconverted\b", sentence, re.I):
                status = "converted"
            elif re.search(r"\brefused\b", sentence, re.I):
                status = "refused"
            else:
                status = "performed"

            node = graph.add_node(
                "Treatment",
                label,
                {"type": treatment_type, "status": status},
            )
            extracted.append(
                ExtractedEntity(node, sentence, match.group(0), start, end)
            )

    return sorted(extracted, key=lambda item: item.char_start)
