"""Extração da entidade Symptom."""

import re

from .common import Mention, detect_polarity, is_hedged, split_sentences

_TRIGGER_PATTERN = re.compile(
    r"(presented with|complains? of|complained of|denies|denied)\s+",
    re.IGNORECASE,
)

_DURATION_PREFIX = re.compile(
    r"^(a\s+)?(?P<value>\d+|one|two|three|four|five|six)[\s-](?P<unit>day|week|month|year)s?\s+history\s+of\s+",
    re.IGNORECASE,
)

_CONNECTOR_PATTERN = re.compile(
    r"\s*(?:,|\band\b|\bor\b|\bassociated with\b)\s*",
    re.IGNORECASE,
)


def extract_symptoms(text: str) -> list[Mention]:
    """Extrai sintomas a partir de gatilhos como 'presented with'/'denies'."""
    mentions = []
    for sentence in split_sentences(text):
        trigger_matches = list(_TRIGGER_PATTERN.finditer(sentence.text))
        for index, match in enumerate(trigger_matches):
            trigger = match.group(1)
            rest_start = match.end()
            rest_end = (
                trigger_matches[index + 1].start()
                if index + 1 < len(trigger_matches)
                else len(sentence.text)
            )
            rest = sentence.text[rest_start:rest_end]

            duration = None
            rest_base = rest_start
            duration_match = _DURATION_PREFIX.match(rest)
            if duration_match is not None:
                duration = f"{duration_match.group('value')} {duration_match.group('unit')}s"
                rest_base += duration_match.end()
                rest = rest[duration_match.end():]

            clause_text = sentence.text[match.start():rest_end]
            polarity = detect_polarity(clause_text)
            hedged = is_hedged(clause_text)

            for cleaned, local_start, _local_end in _split_symptom_spans(rest):
                start = sentence.start + rest_base + local_start
                mentions.append(Mention(
                    node_type="Symptom",
                    label=cleaned,
                    attributes={"polarity": polarity, "duration": duration},
                    sentence=sentence,
                    trigger=trigger,
                    char_start=start,
                    char_end=start + len(cleaned),
                    hedged=hedged,
                ))
    return mentions


def _split_symptom_spans(rest: str) -> list[tuple[str, int, int]]:
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
