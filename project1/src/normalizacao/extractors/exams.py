"""Extração baseada em regras de exames e resultados quantitativos."""

import re
from dataclasses import dataclass

from ..core.graph import GraphBuilder
from ..core.models import Node
from .common import ExtractedEntity
from .results import LabResultCandidate, find_lab_result_candidates


_NAMED_EXAMS = (
    (re.compile(r"\b(?:computed tomography|CT)\b", re.I), "computed tomography", "imaging"),
    (re.compile(r"\b(?:magnetic resonance imaging|MRI)\b", re.I), "magnetic resonance imaging", "imaging"),
    (re.compile(r"\b(?:endoscopic ultrasound|EUS)\b", re.I), "endoscopic ultrasound", "endoscopy"),
    (re.compile(r"\b(?:ultrasonography|ultrasound)\b", re.I), "ultrasound", "imaging"),
    (re.compile(r"\b(?:fine[- ]needle aspiration|FNA)\b", re.I), "fine-needle aspiration", "pathology"),
    (re.compile(r"\bbiopsy\b", re.I), "biopsy", "pathology"),
    (re.compile(r"\bendoscop(?:y|ic examination)\b", re.I), "endoscopy", "endoscopy"),
    (re.compile(r"\b(?:radiograph|x[- ]?ray)\b", re.I), "x-ray", "imaging"),
)

_EXAM_CONTEXT = re.compile(
    r"\b(?:underwent|performed|imaging|scan|study|test|examination|showed|revealed|demonstrated)\b",
    re.I,
)

_ANALYTE_PREFIX = re.compile(
    r"^.*\b(?:showed|revealed|demonstrated|found|with|and|as well as)\s+",
    re.I,
)
_LEADING_RESULT_WORDS = re.compile(
    r"^(?:an?\s+)?(?:elevated|increased|high|decreased|reduced|low|abnormal|normal|positive|negative)\s+",
    re.I,
)
_DISCOURSE_PREFIX = re.compile(r"^(?:later|subsequently|then)\s*,?\s*", re.I)
_ANALYTE_SUFFIX = re.compile(r"\s+(?:level\s+of|of|was|at)\s*$", re.I)


@dataclass(frozen=True)
class ExtractedExamResult:
    """Resultado extraído e o exame laboratorial correspondente."""

    node: Node
    exam_node: Node
    evidence_text: str
    char_start: int
    char_end: int


def _sentence_start(text: str, position: int) -> int:
    boundary = max(
        text.rfind(".", 0, position),
        text.rfind("!", 0, position),
        text.rfind("?", 0, position),
        text.rfind("\n", 0, position),
    )
    return boundary + 1


def _infer_analyte_label(candidate: LabResultCandidate) -> str:
    """Infere o nome do exame a partir do texto antes da medição."""
    relative_start = candidate.measurement.char_start - candidate.char_start
    before = candidate.evidence_text[:relative_start].rstrip(" \t(:,")
    before = _ANALYTE_SUFFIX.sub("", before)
    before = _ANALYTE_PREFIX.sub("", before)
    before = _DISCOURSE_PREFIX.sub("", before)
    before = _LEADING_RESULT_WORDS.sub("", before).strip(" \t,;:")

    # Mantém no máximo seis palavras para evitar carregar a oração inteira.
    words = before.split()
    label = " ".join(words[-6:])
    return label or "laboratory test"


def extract_exams(
    case_text: str,
    graph: GraphBuilder,
) -> list[ExtractedEntity]:
    """Extrai exames nomeados em contextos diagnósticos."""
    if case_text != graph.case_text:
        raise ValueError("case_text and graph use different texts")

    extracted: list[ExtractedEntity] = []

    for pattern, canonical_label, modality in _NAMED_EXAMS:
        for match in pattern.finditer(case_text):
            start = _sentence_start(case_text, match.start())
            end_match = re.search(r"[.!?\n]", case_text[match.end():])
            end = len(case_text) if end_match is None else match.end() + end_match.start()
            sentence = case_text[start:end].strip()

            if _EXAM_CONTEXT.search(sentence) is None:
                continue

            abbreviation = match.group(0) if match.group(0).isupper() else None
            node = graph.add_node(
                "Exam",
                canonical_label,
                {"modality": modality, "abbreviation": abbreviation},
            )
            extracted.append(
                ExtractedEntity(
                    node=node,
                    evidence_text=sentence,
                    trigger=match.group(0),
                    char_start=start,
                    char_end=end,
                )
            )

    return sorted(extracted, key=lambda item: item.char_start)


def extract_exam_results(
    case_text: str,
    graph: GraphBuilder,
) -> list[ExtractedExamResult]:
    """Cria exames laboratoriais e seus resultados quantitativos."""
    if case_text != graph.case_text:
        raise ValueError("case_text and graph use different texts")

    extracted: list[ExtractedExamResult] = []

    for candidate in find_lab_result_candidates(case_text):
        measurement = candidate.measurement.measurement
        reference = (
            candidate.reference_range.reference_range
            if candidate.reference_range is not None
            else None
        )
        exam_node = graph.add_node(
            "Exam",
            _infer_analyte_label(candidate),
            {"modality": "laboratory"},
        )
        result_label = f"{measurement.value}"
        if measurement.unit is not None:
            result_label += f" {measurement.unit}"

        result_node = graph.add_node(
            "ExamResult",
            result_label,
            {
                "value": measurement.value,
                "unit": measurement.unit,
                "reference_range_low": reference.low if reference else None,
                "reference_range_high": reference.high if reference else None,
                "reference_range_raw": reference.raw_text if reference else None,
                "interpretation": candidate.interpretation,
                "interpretation_source": candidate.interpretation_source,
                "raw_text": measurement.raw_text,
            },
            deduplicate=False,
        )
        extracted.append(
            ExtractedExamResult(
                node=result_node,
                exam_node=exam_node,
                evidence_text=candidate.evidence_text,
                char_start=candidate.char_start,
                char_end=candidate.char_end,
            )
        )

    return extracted
