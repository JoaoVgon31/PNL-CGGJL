"""Extração da entidade Diagnosis."""

import re

from .common import Mention, detect_certainty, detect_polarity, is_hedged, split_sentences

_DIAGNOSIS_TRIGGER = re.compile(
    r"(diagnosed with|diagnosis of|consistent with|final pathology revealed)\s+(?P<rest>[^.!?\n]+)",
    re.IGNORECASE,
)


def extract_diagnoses(text: str) -> list[Mention]:
    """Extrai diagnósticos a partir de gatilhos de conclusão clínica."""
    mentions = []
    for sentence in split_sentences(text):
        match = _DIAGNOSIS_TRIGGER.search(sentence.text)
        if match is None:
            continue
        trigger = match.group(1)
        raw_rest = match.group("rest")
        first_segment = re.split(r",| after having| based on| which", raw_rest)[0]
        label = first_segment.strip()
        if not label:
            continue

        certainty = detect_certainty(sentence.text)
        polarity = detect_polarity(sentence.text)
        if "ruled out" in sentence.text.lower():
            certainty = "excluded"
            polarity = "absent"

        role = "differential" if "differential diagnosis" in sentence.text.lower() else "principal"

        start = sentence.start + match.start("rest")
        mentions.append(Mention(
            node_type="Diagnosis",
            label=label,
            attributes={"certainty": certainty, "polarity": polarity, "role": role},
            sentence=sentence,
            trigger=trigger,
            char_start=start,
            char_end=start + len(label),
            hedged=is_hedged(sentence.text),
        ))
    return mentions
