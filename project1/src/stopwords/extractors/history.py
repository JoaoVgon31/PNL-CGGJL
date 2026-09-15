"""Extração da entidade History (antecedentes)."""

import re

from .common import Mention, detect_polarity, is_hedged, split_sentences

_DURATION_HISTORY_OF = re.compile(
    r"\b\d+[\s-](day|week|month|year)s?\s+history\s+of\b",
    re.IGNORECASE,
)

_HISTORY_TRIGGER = re.compile(
    r"(past medical history(?:\s+significant)?(?:\s+for|\s+of)?|family history of|history of)\s+",
    re.IGNORECASE,
)

_FAMILY_TERMS = ("mother", "father", "sibling", "brother", "sister", "family")

_CATEGORY_KEYWORDS = {
    "surgery": ("surgery", "resection", "transplant", "replacement", "operation"),
    "exposure": ("smoking", "alcohol", "exposure", "occupational"),
    "medication": ("therapy", "medication"),
}

_CONNECTOR_PATTERN = re.compile(r"\s*(?:,|\band\b)\s*", re.IGNORECASE)


def extract_history(text: str) -> list[Mention]:
    """Extrai antecedentes, evitando o gatilho de duração de sintoma atual."""
    mentions = []
    for sentence in split_sentences(text):
        if _DURATION_HISTORY_OF.search(sentence.text):
            continue

        trigger_matches = list(_HISTORY_TRIGGER.finditer(sentence.text))
        for index, match in enumerate(trigger_matches):
            trigger = match.group(1)
            rest_start = match.end()
            rest_end = (
                trigger_matches[index + 1].start()
                if index + 1 < len(trigger_matches)
                else len(sentence.text)
            )
            rest = sentence.text[rest_start:rest_end]

            clause_text = sentence.text[match.start():rest_end]
            subject = "family" if any(term in clause_text.lower() for term in _FAMILY_TERMS) else "patient"
            polarity = detect_polarity(clause_text)
            hedged = is_hedged(clause_text)

            for cleaned, local_start, _local_end in _split_history_spans(rest):
                start = sentence.start + rest_start + local_start
                mentions.append(Mention(
                    node_type="History",
                    label=cleaned,
                    attributes={
                        "subject": subject,
                        "polarity": polarity,
                        "category": _infer_category(cleaned),
                    },
                    sentence=sentence,
                    trigger=trigger.strip(),
                    char_start=start,
                    char_end=start + len(cleaned),
                    hedged=hedged,
                ))
    return mentions


def _split_history_spans(rest: str) -> list[tuple[str, int, int]]:
    """Divide rest em (texto, local_start, local_end), preservando offsets."""
    spans = []
    pos = 0
    for match in _CONNECTOR_PATTERN.finditer(rest):
        piece = rest[pos:match.start()]
        cleaned = piece.strip()
        if cleaned:
            local_start = pos + piece.find(cleaned)
            spans.append((cleaned, local_start, local_start + len(cleaned)))
        pos = match.end()
    piece = rest[pos:]
    cleaned = piece.strip()
    if cleaned:
        local_start = pos + piece.find(cleaned)
        spans.append((cleaned, local_start, local_start + len(cleaned)))
    return spans


def _infer_category(label: str) -> str:
    lowered = label.lower()
    for category, keywords in _CATEGORY_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return category
    return "condition"
