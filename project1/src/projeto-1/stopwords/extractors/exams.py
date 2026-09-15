"""Extração de Exam e ExamResult."""

import re

from .common import Mention, split_sentences

_EXAM_TRIGGER = re.compile(
    r"(underwent|performed)\s+(?P<rest>[^.!?\n]+)",
    re.IGNORECASE,
)

_ABBREVIATION_PATTERN = re.compile(r"\(([A-Z]{2,6})\)")

_MODALITY_KEYWORDS = {
    "imaging": ("tomography", "ct", "mri", "ultrasound", "x-ray", "imaging"),
    "endoscopy": ("endoscopy",),
    "pathology": ("pathology", "biopsy"),
    "laboratory": ("laboratory", "blood test", "antigen", "testing"),
    "functional": ("function test",),
}

_RESULT_PATTERN = re.compile(
    r"(?P<label>[A-Za-z][\w\s-]*?)\s+(?:level\s+of|of|was)\s+"
    r"(?P<value>\d[\d,]*\.?\d*|positive|negative)\s*"
    r"(?P<unit>ng/ml|u/l|mg/dl|g/dl|mmol/l|mm/h|%|/µl|/ul)?",
    re.IGNORECASE,
)

_REFERENCE_RANGE_PATTERN = re.compile(
    r"normal range,?\s*(?P<raw>[<>=]?\s*[\d.]+\s*-?\s*[\d.]*)",
    re.IGNORECASE,
)

_INTERPRETATION_KEYWORDS = {
    "normal": ("normal",),
    "elevated": ("elevated", "high"),
    "decreased": ("decreased", "low"),
    "abnormal": ("abnormal",),
    "positive": ("positive",),
    "negative": ("negative",),
}


def extract_exams(text: str) -> list[Mention]:
    """Extrai exames a partir de 'underwent'/'performed'."""
    mentions = []
    for sentence in split_sentences(text):
        match = _EXAM_TRIGGER.search(sentence.text)
        if match is None:
            continue
        trigger = match.group(1)
        raw_rest = match.group("rest")
        first_segment = re.split(r",| and ", raw_rest)[0].strip()
        label = first_segment
        if not label:
            continue

        abbreviation_match = _ABBREVIATION_PATTERN.search(sentence.text)
        local_offset = first_segment.find(label)
        start = sentence.start + match.start("rest") + local_offset
        mentions.append(Mention(
            node_type="Exam",
            label=label,
            attributes={
                "modality": _infer_modality(label),
                "abbreviation": abbreviation_match.group(1) if abbreviation_match else None,
                "contrast": True if "contrast" in sentence.text.lower() else None,
            },
            sentence=sentence,
            trigger=trigger,
            char_start=start,
            char_end=start + len(label),
            hedged=False,
        ))
    return mentions


def extract_exam_results(text: str) -> list[Mention]:
    """Extrai valor + unidade de resultados de exame."""
    mentions = []
    for sentence in split_sentences(text):
        match = _RESULT_PATTERN.search(sentence.text)
        if match is None:
            continue
        label = match.group("label").strip()
        if not label or len(label.split()) > 6:
            continue

        value = match.group("value")
        unit = match.group("unit")
        range_match = _REFERENCE_RANGE_PATTERN.search(sentence.text)

        start = sentence.start + match.start("value")
        mentions.append(Mention(
            node_type="ExamResult",
            label=label,
            attributes={
                "value": value,
                "unit": unit.lower() if unit else None,
                "reference_range_raw": range_match.group("raw").strip() if range_match else None,
                "interpretation": _infer_interpretation(sentence.text),
                "raw_text": match.group(0).strip(),
            },
            sentence=sentence,
            trigger="level of" if "level of" in sentence.text.lower() else "of",
            char_start=start,
            char_end=start + len(value),
            hedged=False,
        ))
    return mentions


def _infer_modality(label: str) -> str | None:
    lowered = label.lower()
    for modality, keywords in _MODALITY_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return modality
    return None


def _infer_interpretation(sentence_text: str) -> str | None:
    lowered = sentence_text.lower()
    for interpretation, keywords in _INTERPRETATION_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return interpretation
    return None
