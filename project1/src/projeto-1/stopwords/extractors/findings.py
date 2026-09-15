"""Extração da entidade Finding."""

import re

from .common import Mention, detect_certainty, detect_polarity, is_hedged, split_sentences

_FINDING_TRIGGER = re.compile(
    r"(demonstrat\w*|reveal\w*|showed|noted|on examination,?)\s+(?P<rest>[^.!?\n]+)",
    re.IGNORECASE,
)

_SIZE_PATTERN = re.compile(
    r"\d+(\.\d+)?\s*(x\s*\d+(\.\d+)?\s*)*(cm|mm)\b",
    re.IGNORECASE,
)

_SOURCE_KEYWORDS = {
    "imaging": ("ct", "mri", "ultrasound", "imaging", "computed tomography"),
    "pathology": ("pathology", "biopsy", "histology"),
    "lab": ("laboratory", "blood test"),
    "endoscopy": ("endoscopy", "endoscopic"),
    "physical_exam": ("on examination", "physical exam"),
}


def extract_findings(text: str) -> list[Mention]:
    """Extrai achados a partir de verbos de achado ('demonstrated', 'revealed'...)."""
    mentions = []
    for sentence in split_sentences(text):
        match = _FINDING_TRIGGER.search(sentence.text)
        if match is None:
            continue

        trigger = match.group(1)
        rest = match.group("rest").strip()
        if not rest:
            continue

        size_match = _SIZE_PATTERN.search(rest)
        size = size_match.group(0) if size_match else None

        raw_segment = rest.split(",")[0]
        label = raw_segment.strip()
        if not label:
            continue
        local_offset = raw_segment.find(label)
        start = sentence.start + match.start("rest") + local_offset
        mentions.append(Mention(
            node_type="Finding",
            label=label,
            attributes={
                "source": _infer_source(sentence.text),
                "polarity": detect_polarity(sentence.text),
                "certainty": detect_certainty(sentence.text),
                "size": size,
            },
            sentence=sentence,
            trigger=trigger.strip(),
            char_start=start,
            char_end=start + len(label),
            hedged=is_hedged(sentence.text),
        ))
    return mentions


def _infer_source(sentence_text: str) -> str | None:
    lowered = sentence_text.lower()
    for source, keywords in _SOURCE_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return source
    return None
