"""Orquestração do pipeline caso clínico para grafo."""

from dataclasses import dataclass
from pathlib import Path

from .case_reader import ClinicalCase, read_case
from .core.graph import GraphBuilder
from .extractors.diagnoses import extract_diagnoses
from .extractors.exams import extract_exam_results, extract_exams
from .extractors.findings import extract_findings
from .extractors.history import extract_history
from .extractors.outcomes import extract_outcomes
from .extractors.patient import extract_patient
from .extractors.relations import ExtractedCaseEntities, build_relations
from .extractors.symptoms import extract_symptoms
from .extractors.treatments import extract_medications, extract_treatments


@dataclass(frozen=True)
class PipelineResult:
    """Resultado completo do processamento de um caso."""

    case: ClinicalCase
    graph: GraphBuilder
    entities: ExtractedCaseEntities


def process_case(case: ClinicalCase) -> PipelineResult:
    """Executa extração, normalização, deduplicação e relações."""
    graph = GraphBuilder(case.case_id, case.case_text)
    patient = extract_patient(case, graph)

    entities = ExtractedCaseEntities(
        patient=patient,
        symptoms=tuple(extract_symptoms(case.case_text, graph)),
        histories=tuple(extract_history(case.case_text, graph)),
        exams=tuple(extract_exams(case.case_text, graph)),
        exam_results=tuple(extract_exam_results(case.case_text, graph)),
        findings=tuple(extract_findings(case.case_text, graph)),
        diagnoses=tuple(extract_diagnoses(case.case_text, graph)),
        medications=tuple(extract_medications(case.case_text, graph)),
        treatments=tuple(extract_treatments(case.case_text, graph)),
        outcomes=tuple(extract_outcomes(case.case_text, graph)),
    )
    build_relations(graph, entities)
    return PipelineResult(case=case, graph=graph, entities=entities)


def process_case_from_csv(
    csv_path: str | Path,
    case_id: str,
) -> PipelineResult:
    """Lê e processa um caso identificado no CSV."""
    return process_case(read_case(csv_path, case_id))
