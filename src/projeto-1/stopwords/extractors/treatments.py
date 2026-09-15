"""Extração de Treatment e Medication."""

import re

from .common import Mention, split_sentences

_TREATMENT_TRIGGER = re.compile(
    r"(?:(?P<trigger1>underwent|was treated with|treated with)\s+(?P<rest>[^.!?\n]+))"
    r"|(?:(?P<treatment>[^.!?\n]+?)\s+(?P<trigger2>was planned|was converted|was refused))",
    re.IGNORECASE,
)

_SURGERY_KEYWORDS = ("resection", "surgery", "pancreatectomy", "transplant", "laparoscopic")

_STATUS_KEYWORDS = {
    "planned": ("was planned", "planned"),
    "converted": ("converted",),
    "refused": ("refused",),
}

_MEDICATION_PATTERN = re.compile(
    r"(?P<drug>[A-Za-z][\w-]*)\s+(?P<dose>\d+(?:\.\d+)?)\s*(?P<unit>mg|g|mcg|iu|ml|units)\b"
    r"(?:\s+(?P<frequency>once daily|twice daily|three times daily|four times daily|as needed))?",
    re.IGNORECASE,
)

_ROUTE_KEYWORDS = {
    "oral": ("oral", "by mouth"),
    "intravenous": ("intravenous", "iv "),
    "intramuscular": ("intramuscular",),
    "subcutaneous": ("subcutaneous",),
    "topical": ("topical",),
    "inhaled": ("inhaled",),
}

_MEDICATION_STOP_WORDS = {"a", "the", "was", "dose", "dosage", "of"}


def extract_treatments(text: str) -> list[Mention]:
    """Extrai tratamentos não-farmacológicos (cirurgia, procedimento)."""
    mentions = []
    for sentence in split_sentences(text):
        match = _TREATMENT_TRIGGER.search(sentence.text)
        if match is None:
            continue

        if match.group("rest") is not None:
            trigger = match.group("trigger1")
            raw_rest = match.group("rest")
            start_offset = match.start("rest")
        else:
            trigger = match.group("trigger2")
            raw_rest = match.group("treatment")
            start_offset = match.start("treatment")

        first_segment = re.split(r",| and ", raw_rest)[0]
        label = first_segment.strip()
        if not label or _MEDICATION_PATTERN.search(label):
            continue

        lowered = sentence.text.lower()
        treatment_type = "surgery" if any(k in label.lower() for k in _SURGERY_KEYWORDS) else "procedure"
        status = "performed"
        for status_value, keywords in _STATUS_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                status = status_value
                break

        start = sentence.start + start_offset
        mentions.append(Mention(
            node_type="Treatment",
            label=label,
            attributes={"type": treatment_type, "status": status},
            sentence=sentence,
            trigger=trigger,
            char_start=start,
            char_end=start + len(label),
            hedged=False,
        ))
    return mentions


def extract_medications(text: str) -> list[Mention]:
    """Extrai medicamentos a partir do padrão <droga> <dose><unidade> <frequência>."""
    mentions = []
    for sentence in split_sentences(text):
        for match in _MEDICATION_PATTERN.finditer(sentence.text):
            drug = match.group("drug")
            if drug.lower() in _MEDICATION_STOP_WORDS:
                continue

            lowered = sentence.text.lower()
            route = None
            for route_value, keywords in _ROUTE_KEYWORDS.items():
                if any(keyword in lowered for keyword in keywords):
                    route = route_value
                    break

            start = sentence.start + match.start("drug")
            mentions.append(Mention(
                node_type="Medication",
                label=drug,
                attributes={
                    "dose_value": match.group("dose"),
                    "dose_unit": match.group("unit").lower(),
                    "frequency": match.group("frequency"),
                    "route": route,
                },
                sentence=sentence,
                trigger=match.group(0),
                char_start=start,
                char_end=start + len(drug),
                hedged=False,
            ))
    return mentions
