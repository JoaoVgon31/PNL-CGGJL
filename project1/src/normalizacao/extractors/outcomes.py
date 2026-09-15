"""Extração baseada em regras de desfechos clínicos."""

import re

from ..core.graph import GraphBuilder
from .common import ExtractedEntity


_OUTCOME_PATTERNS = (
    (re.compile(r"\bdischarged(?:\s+home)?\b", re.I), "discharged home", "discharge"),
    (re.compile(r"\b(?:expired|died|death)\b", re.I), "death", "death"),
    (re.compile(r"\b(?:complete\s+)?resolution(?:\s+of\s+(?:symptoms|pain|nausea))?\b", re.I), "symptom resolution", "resolution"),
    (re.compile(r"\b(?:improved|improvement)\b", re.I), "clinical improvement", "improvement"),
    (re.compile(r"\brecurrence\b", re.I), "recurrence", "recurrence"),
    (re.compile(r"\bcomplications?\b", re.I), "complication", "complication"),
)
_NEGATED_OUTCOME = re.compile(r"\b(?:no evidence of|without|no)\s+$", re.I)
_POSTOPERATIVE_DAY = re.compile(r"\bpostoperative\s+day\s+(\d+)\b", re.I)
_DISCHARGE_DAY = re.compile(r"\bdischarged(?:\s+home)?\s+(?:on\s+)?day\s+(\d+)\b", re.I)
_FOLLOW_UP = re.compile(r"\b(?:at|after)\s+(\d+)\s+(days?|weeks?|months?|years?)\s+(?:of\s+)?follow[- ]?up\b", re.I)


def _sentence_bounds(text: str, position: int) -> tuple[int, int]:
    start = max(text.rfind(mark, 0, position) for mark in ".!?\n") + 1
    endings = [index for mark in ".!?\n" if (index := text.find(mark, position)) >= 0]
    end = min(endings) if endings else len(text)
    return start, end


def extract_outcomes(case_text: str, graph: GraphBuilder) -> list[ExtractedEntity]:
    """Extrai desfechos declarados explicitamente no caso."""
    if case_text != graph.case_text:
        raise ValueError("case_text and graph use different texts")

    extracted: list[tuple[int, ExtractedEntity]] = []
    for pattern, label, outcome_type in _OUTCOME_PATTERNS:
        for match in pattern.finditer(case_text):
            start, end = _sentence_bounds(case_text, match.start())
            sentence = case_text[start:end].strip()
            preceding = case_text[max(start, match.start() - 30):match.start()]
            polarity = "absent" if _NEGATED_OUTCOME.search(preceding) else "present"
            postoperative = _POSTOPERATIVE_DAY.search(sentence)
            discharge_day = _DISCHARGE_DAY.search(sentence)
            follow_up = _FOLLOW_UP.search(sentence)

            timing = None
            length_of_stay = None
            follow_up_duration = None
            if postoperative:
                timing = f"postoperative day {postoperative.group(1)}"
            if discharge_day:
                length_of_stay = f"{discharge_day.group(1)} days"
            elif outcome_type == "discharge" and postoperative:
                length_of_stay = f"{postoperative.group(1)} days"
            if follow_up:
                follow_up_duration = f"{follow_up.group(1)} {follow_up.group(2).casefold()}"

            node = graph.add_node(
                "Outcome",
                label,
                {
                    "type": outcome_type,
                    "timing": timing,
                    "length_of_stay": length_of_stay,
                    "follow_up_duration": follow_up_duration,
                    "polarity": polarity,
                },
            )
            extracted.append(
                (
                    match.start(),
                    ExtractedEntity(node, sentence, match.group(0), start, end),
                )
            )

    return [
        entity
        for _, entity in sorted(extracted, key=lambda item: item[0])
    ]
