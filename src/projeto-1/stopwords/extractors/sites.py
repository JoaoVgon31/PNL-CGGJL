"""Extração da entidade AnatomicalSite via léxico fechado de órgãos/regiões."""

import re

from .common import Mention, split_sentences

_SITE_TERMS = (
    "sylvian fissure", "gallbladder", "stomach", "pancreas", "liver", "lung",
    "kidney", "brain", "heart", "colon", "breast", "ovary", "prostate",
    "spleen", "mediastinum", "bladder", "uterus", "thyroid", "esophagus",
    "duodenum", "appendix", "rectum",
)

_SITE_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(term) for term in _SITE_TERMS) + r")\b",
    re.IGNORECASE,
)

_LATERALITY_PATTERN = re.compile(r"\b(left|right|bilateral)\b", re.IGNORECASE)
_QUALIFIER_TERMS = ("upper", "lower", "proximal", "distal", "anterior", "posterior", "body/tail")
_QUALIFIER_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(term) for term in _QUALIFIER_TERMS) + r")\b",
    re.IGNORECASE,
)


def extract_sites(text: str) -> list[Mention]:
    """Extrai sítios anatômicos e seus modificadores de lateralidade/região."""
    mentions = []
    for sentence in split_sentences(text):
        previous_end = 0
        for match in _SITE_PATTERN.finditer(sentence.text):
            label = match.group(0).lower()
            window_start = max(previous_end, match.start() - 20)
            window = sentence.text[window_start:match.start()]

            laterality_match = _LATERALITY_PATTERN.search(window)
            qualifier_match = _QUALIFIER_PATTERN.search(window)

            start = sentence.start + match.start()
            mentions.append(Mention(
                node_type="AnatomicalSite",
                label=label,
                attributes={
                    "laterality": laterality_match.group(1).lower() if laterality_match else None,
                    "region_qualifier": qualifier_match.group(1).lower() if qualifier_match else None,
                },
                sentence=sentence,
                trigger=label,
                char_start=start,
                char_end=start + len(label),
                hedged=False,
            ))
            previous_end = match.end()
    return mentions
