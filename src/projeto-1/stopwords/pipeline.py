"""Orquestração do pipeline caso clínico -> grafo, com as 4 condições de stop-words."""

from dataclasses import dataclass

from .case_reader import ClinicalCase, read_case
from .core.graph import GraphBuilder
from .core.models import Node
from .experiment.conditions import Condition
from .extractors import diagnoses as diagnoses_ext
from .extractors import exams as exams_ext
from .extractors import findings as findings_ext
from .extractors import history as history_ext
from .extractors import outcomes as outcomes_ext
from .extractors import patient as patient_ext
from .extractors import relations as relations_ext
from .extractors import sites as sites_ext
from .extractors import symptoms as symptoms_ext
from .extractors import treatments as treatments_ext
from .extractors.common import Mention
from .lexicon.label_cleaning import clean_label
from .lexicon.loader import load_list
from .lexicon.masking import mask_text

_EXTRACTOR_CALLS = (
    ("Symptom", symptoms_ext.extract_symptoms),
    ("History", history_ext.extract_history),
    ("Finding", findings_ext.extract_findings),
    ("Exam", exams_ext.extract_exams),
    ("ExamResult", exams_ext.extract_exam_results),
    ("Diagnosis", diagnoses_ext.extract_diagnoses),
    ("Treatment", treatments_ext.extract_treatments),
    ("Medication", treatments_ext.extract_medications),
    ("AnatomicalSite", sites_ext.extract_sites),
    ("Outcome", outcomes_ext.extract_outcomes),
)


@dataclass(frozen=True)
class PipelineResult:
    """Resultado do processamento de um caso: o caso de entrada e o grafo gerado."""

    case: ClinicalCase
    graph: GraphBuilder


def _text_for_extraction(case_text: str, condition: Condition, wordlist: str | None) -> str:
    if condition in (Condition.BASELINE, Condition.GUARDED_LABEL):
        return case_text

    remove_words = load_list(wordlist)
    if condition is Condition.NAIVE_UNPROTECTED:
        return mask_text(case_text, remove_words, frozenset())

    protect_words = load_list("protection_list")
    return mask_text(case_text, remove_words, protect_words)


def _finalize_label(label: str, condition: Condition, wordlist: str | None) -> str:
    if condition is not Condition.GUARDED_LABEL:
        return label

    remove_words = load_list(wordlist)
    protect_words = load_list("protection_list")
    return clean_label(label, remove_words, protect_words)


def process_case(
    case: ClinicalCase,
    condition: Condition = Condition.BASELINE,
    wordlist: str | None = None,
) -> PipelineResult:
    """Roda a extração completa sobre um caso, numa das 4 condições de stop-words."""
    if condition is not Condition.BASELINE and wordlist is None:
        raise ValueError("wordlist is required for every condition except BASELINE")

    text = _text_for_extraction(case.case_text, condition, wordlist)
    graph = GraphBuilder(case.case_id)

    patient_attributes = patient_ext.extract_patient_attributes(case, text)
    graph.add_node("Patient", "patient", patient_attributes)
    patient_id = next(node.node_id for node in graph.nodes if node.type == "Patient")

    mentions_by_type: dict[str, list[tuple[Mention, Node]]] = {}
    for node_type, extractor in _EXTRACTOR_CALLS:
        pairs = []
        for mention in extractor(text):
            label = _finalize_label(mention.label, condition, wordlist)
            node = graph.add_node(mention.node_type, label, dict(mention.attributes))
            pairs.append((mention, node))
        mentions_by_type[node_type] = pairs

    relations_ext.build_relations(graph, patient_id, mentions_by_type)

    return PipelineResult(case=case, graph=graph)


def process_case_from_csv(
    csv_path,
    case_id: str,
    condition: Condition = Condition.BASELINE,
    wordlist: str | None = None,
) -> PipelineResult:
    """Lê um caso do CSV e roda process_case sobre ele."""
    return process_case(read_case(csv_path, case_id), condition, wordlist)
