"""Extração da entidade Outcome."""

import re

from .common import Mention, detect_polarity, split_sentences

_OUTCOME_KEYWORDS = {
    "death": ("expired", "died", "death"),
    "discharge": ("discharged",),
    "resolution": ("resolution", "resolved"),
    "recurrence": ("recurrence", "recurred"),
    "improvement": ("improved", "improvement"),
    "complication": ("complication",),
}

_OUTCOME_PATTERNS = {
    candidate_type: re.compile(
        r"\b(?:" + "|".join(re.escape(keyword) for keyword in keywords) + r")\b",
        re.IGNORECASE,
    )
    for candidate_type, keywords in _OUTCOME_KEYWORDS.items()
}

_DURATION_PATTERN = re.compile(
    r"(postoperative day\s+\d+|\d+\s*(day|week|month|year)s?)",
    re.IGNORECASE,
)


def extract_outcomes(text: str) -> list[Mention]:
    """Extrai o desfecho do caso, preferindo o que vem após uma adversativa."""
    mentions = []
    for sentence in split_sentences(text):
        lowered = sentence.text.lower()
        search_text = lowered
        offset = 0
        for connector in (" but ", " later "):
            if connector in search_text:
                tail = search_text.rsplit(connector, 1)[-1]
                offset = len(sentence.text) - len(tail)
                search_text = tail

        outcome_type = None
        match_in_search_text = None
        for candidate_type, pattern in _OUTCOME_PATTERNS.items():
            match = pattern.search(search_text)
            if match is not None:
                outcome_type = candidate_type
                match_in_search_text = match
                break

        if outcome_type is None:
            continue

        matched_keyword = match_in_search_text.group(0)
        duration_match = _DURATION_PATTERN.search(sentence.text)
        duration = duration_match.group(0) if duration_match else None

        start = sentence.start + offset + match_in_search_text.start()
        mentions.append(Mention(
            node_type="Outcome",
            label=matched_keyword,
            attributes={
                "type": outcome_type,
                "polarity": detect_polarity(sentence.text),
                "timing": duration,
                "length_of_stay": duration if outcome_type == "discharge" else None,
            },
            sentence=sentence,
            trigger=matched_keyword,
            char_start=start,
            char_end=start + len(matched_keyword),
            hedged=False,
        ))
    return mentions
