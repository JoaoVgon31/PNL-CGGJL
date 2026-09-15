"""Extração baseada em regras de achados e sítios anatômicos."""

import re
from dataclasses import dataclass

from ..core.graph import GraphBuilder
from ..core.models import Node
from .common import ExtractedEntity


_FINDING_TRIGGER = re.compile(
    r"\b(?:showed|demonstrated|revealed|confirmed|found|noted|examination)\b",
    re.I,
)
_FINDING = re.compile(
    r"\b(?P<label>(?:[A-Za-z]+(?:-[A-Za-z]+)?\s+){0,4}"
    r"(?:lesion|mass|cyst|pseudocyst|tenderness|edema|stranding|abscess|"
    r"malignancy|abnormality|abnormalities|bleeding|leak))\b",
    re.I,
)
_FINDING_LEADING = re.compile(
    r"^.*\b(?:showed|demonstrated|revealed|confirmed|found|noted|examination)\s+",
    re.I,
)
_NEGATION = re.compile(r"\b(?:no evidence of|without|excluded|free of)\b", re.I)
_SIZE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:x\s*\d+(?:\.\d+)?\s*){0,2}(?:cm|mm)\b",
    re.I,
)
_ANATOMICAL_SITES = {
    "stomach": re.compile(r"\bstomach\b", re.I),
    "pancreas": re.compile(r"\bpancrea(?:s|tic)\b", re.I),
    "duodenum": re.compile(r"\bduoden(?:um|al)\b", re.I),
    "liver": re.compile(r"\b(?:liver|hepatic)\b", re.I),
    "lung": re.compile(r"\b(?:lung|pulmonary)\b", re.I),
    "kidney": re.compile(r"\b(?:kidney|renal)\b", re.I),
    "colon": re.compile(r"\b(?:colon|colonic)\b", re.I),
    "brain": re.compile(r"\b(?:brain|cerebral)\b", re.I),
    "abdomen": re.compile(r"\babdom(?:en|inal)\b", re.I),
    "chest": re.compile(r"\bchest\b", re.I),
}


@dataclass(frozen=True)
class ExtractedFinding:
    """Achado e sítios anatômicos mencionados na mesma sentença."""

    entity: ExtractedEntity
    anatomical_sites: tuple[Node, ...]


def _sentence_spans(text: str):
    start = 0
    for boundary in re.finditer(r"\.(?!\d)|[!?]|\n+", text):
        end = boundary.start()
        if text[start:end].strip():
            yield start, end
        start = boundary.end()
    if text[start:].strip():
        yield start, len(text)


def _finding_source(sentence: str) -> str:
    if re.search(r"\b(?:CT|MRI|imaging|tomography|ultrasound)\b", sentence, re.I):
        return "imaging"
    if re.search(r"\b(?:pathology|biopsy|FNA)\b", sentence, re.I):
        return "pathology"
    if re.search(r"\b(?:endoscopy|endoscopic)\b", sentence, re.I):
        return "endoscopy"
    if re.search(r"\b(?:surgery|surgical|intraoperative)\b", sentence, re.I):
        return "surgical"
    if re.search(r"\b(?:physical|on examination)\b", sentence, re.I):
        return "physical_exam"
    return "lab"


def _site_attributes(sentence: str, match: re.Match[str]) -> dict[str, str | None]:
    nearby = sentence[max(0, match.start() - 30):match.end() + 30]
    laterality_match = re.search(r"\b(left|right|bilateral)\b", nearby, re.I)
    region_match = re.search(
        r"\b(upper|lower|proximal|distal|anterior|posterior|body/tail|tail)\b",
        nearby,
        re.I,
    )
    return {
        "laterality": laterality_match.group(1).casefold() if laterality_match else None,
        "region_qualifier": region_match.group(1).casefold() if region_match else None,
    }


def extract_findings(
    case_text: str,
    graph: GraphBuilder,
) -> list[ExtractedFinding]:
    """Extrai achados e localizações em sentenças com evidência explícita."""
    if case_text != graph.case_text:
        raise ValueError("case_text and graph use different texts")

    extracted: list[ExtractedFinding] = []
    for start, end in _sentence_spans(case_text):
        sentence = case_text[start:end].strip()
        if _FINDING_TRIGGER.search(sentence) is None:
            continue

        sites: list[Node] = []
        for site_label, pattern in _ANATOMICAL_SITES.items():
            for site_match in pattern.finditer(sentence):
                sites.append(
                    graph.add_node(
                        "AnatomicalSite",
                        site_label,
                        _site_attributes(sentence, site_match),
                    )
                )

        for match in _FINDING.finditer(sentence):
            label = _FINDING_LEADING.sub("", match.group("label"))
            label = re.sub(r"^(?:a|an|the)\s+", "", label, flags=re.I).strip()
            label = re.sub(r"^(?:cm|mm)\s+", "", label, flags=re.I)
            label = _NEGATION.sub("", label).strip()
            preceding = sentence[max(0, match.start() - 40):match.start()]
            polarity_context = f"{preceding} {match.group('label')}"
            polarity = (
                "absent" if _NEGATION.search(polarity_context) else "present"
            )
            size_context = sentence[max(0, match.start() - 40):match.end()]
            size_matches = list(_SIZE.finditer(size_context))
            size = size_matches[-1].group(0) if size_matches else None
            node = graph.add_node(
                "Finding",
                label,
                {
                    "source": _finding_source(sentence),
                    "polarity": polarity,
                    "certainty": "confirmed",
                    "size": size,
                },
            )
            entity = ExtractedEntity(
                node=node,
                evidence_text=sentence,
                trigger=_FINDING_TRIGGER.search(sentence).group(0),
                char_start=start,
                char_end=end,
            )
            extracted.append(ExtractedFinding(entity=entity, anatomical_sites=tuple(sites)))

    return extracted
