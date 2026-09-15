from __future__ import annotations

from pathlib import Path
from typing import Any

from case_reader import ClinicalCase, read_case
from concepts import link_entities_to_concepts
from core.graph import GraphBuilder
from core.models import Node
from extractors.anatomical_site import extract_anatomical_sites
from extractors.common import ExtractedEntity
from extractors.diagnoses import extract_diagnoses
from extractors.history import extract_history
from extractors.medications import extract_medications
from extractors.outcomes import extract_outcomes
from extractors.patient import extract_patient
from extractors.procedures import extract_exams_and_treatments
from extractors.symptoms import extract_symptoms
from mesh_parser import load_gazetteer_rows, rows_to_raw_gazetteer
from normalization import build_normalized_gazetteer

GAZETTEER_CSVS = [
    Path(__file__).parent / "gazetteer" / "mesh_gazetteer.csv",
    Path(__file__).parent / "gazetteer" / "anatomical_site_gazetteer.csv",
]


def _edge_attrs(entity: ExtractedEntity) -> dict[str, Any]:
    return {
        "evidence_text": entity.evidence_text,
        "trigger": entity.trigger,
        "char_start": entity.char_start,
        "char_end": entity.char_end,
    }


def load_gazetteers_by_category(
    csv_paths: list[str | Path] = GAZETTEER_CSVS,
) -> dict[str, dict[str, list[tuple[str, str]]]]:
    rows: list[dict[str, str]] = []
    for csv_path in csv_paths:
        rows.extend(load_gazetteer_rows(csv_path))
    categories = {row["category"] for row in rows}
    return {
        category: build_normalized_gazetteer(rows_to_raw_gazetteer(rows, category=category))
        for category in categories
    }


def process_case(
    case: ClinicalCase,
    gazetteers: dict[str, dict[str, list[tuple[str, str]]]] | None = None,
) -> GraphBuilder:
    if gazetteers is None:
        gazetteers = load_gazetteers_by_category()

    graph = GraphBuilder(case.case_id, case.case_text)
    patient = extract_patient(case, graph)

    symptoms = extract_symptoms(case.case_text, graph)
    histories = extract_history(case.case_text, graph)
    diagnoses = extract_diagnoses(case.case_text, graph)
    exams, treatments = extract_exams_and_treatments(case.case_text, graph)
    medications = extract_medications(case.case_text, graph)
    outcomes = extract_outcomes(case.case_text, graph)

    for entity in symptoms:
        graph.add_edge(patient, entity.node, "HAS_SYMPTOM", _edge_attrs(entity))
    for entity in histories:
        graph.add_edge(patient, entity.node, "HAS_HISTORY", _edge_attrs(entity))
    for entity in diagnoses:
        graph.add_edge(patient, entity.node, "DIAGNOSED_WITH", _edge_attrs(entity))
    for entity in exams:
        graph.add_edge(patient, entity.node, "UNDERWENT_EXAM", _edge_attrs(entity))
    for entity in treatments:
        graph.add_edge(patient, entity.node, "TREATED_WITH", _edge_attrs(entity))
    for entity in medications:
        graph.add_edge(patient, entity.node, "TREATED_WITH", _edge_attrs(entity))
    for entity in outcomes:
        graph.add_edge(patient, entity.node, "HAS_OUTCOME", _edge_attrs(entity))

    anatomical_sites = extract_anatomical_sites(
        case.case_text,
        graph,
        gazetteers.get("anatomical_site", {}),
        diagnosis_entities=diagnoses,
        anchor_entities=symptoms + treatments,
    )

    concept_nodes: dict[str, Node] = {}
    diseases = gazetteers.get("diseases", {})
    mental = gazetteers.get("mental_disorders", {})
    link_entities_to_concepts(symptoms, [diseases], graph, concept_nodes)
    link_entities_to_concepts(histories, [diseases], graph, concept_nodes)
    link_entities_to_concepts(diagnoses, [diseases, mental], graph, concept_nodes)
    link_entities_to_concepts(exams, [gazetteers.get("exams", {})], graph, concept_nodes)
    link_entities_to_concepts(treatments, [gazetteers.get("treatments", {})], graph, concept_nodes)
    link_entities_to_concepts(medications, [gazetteers.get("drugs", {})], graph, concept_nodes)
    link_entities_to_concepts(
        anatomical_sites,
        [gazetteers.get("anatomical_site", {})],
        graph,
        concept_nodes,
        vocabulary="local",
    )

    return graph


def process_case_from_csv(
    csv_path: str | Path,
    case_id: str,
    gazetteers: dict[str, dict[str, list[tuple[str, str]]]] | None = None,
) -> GraphBuilder:
    case = read_case(csv_path, case_id)
    return process_case(case, gazetteers)
