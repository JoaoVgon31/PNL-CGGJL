"""Testes da criação de relações do grafo."""


import unittest
from decimal import Decimal


from normalizacao.case_reader import ClinicalCase
from normalizacao.extractors.diagnoses import extract_diagnoses
from normalizacao.extractors import extract_history, extract_patient, extract_symptoms
from normalizacao.extractors.exams import extract_exam_results, extract_exams
from normalizacao.extractors.findings import extract_findings
from normalizacao.core.graph import GraphBuilder
from normalizacao.extractors.outcomes import extract_outcomes
from normalizacao.extractors.relations import ExtractedCaseEntities, build_relations
from normalizacao.extractors.treatments import extract_medications, extract_treatments


def _build(text: str):
    case = ClinicalCase("PMC5137649", Decimal("44"), "PMC5137649_01", text, "Female")
    graph = GraphBuilder(case.case_id, case.case_text)
    patient = extract_patient(case, graph)
    entities = ExtractedCaseEntities(
        patient=patient,
        symptoms=tuple(extract_symptoms(text, graph)),
        histories=tuple(extract_history(text, graph)),
        exams=tuple(extract_exams(text, graph)),
        exam_results=tuple(extract_exam_results(text, graph)),
        findings=tuple(extract_findings(text, graph)),
        diagnoses=tuple(extract_diagnoses(text, graph)),
        medications=tuple(extract_medications(text, graph)),
        treatments=tuple(extract_treatments(text, graph)),
        outcomes=tuple(extract_outcomes(text, graph)),
    )
    build_relations(graph, entities)
    return graph


class RelationExtractionTests(unittest.TestCase):
    def test_builds_direct_and_structural_relations(self):
        text = (
            "A 44-year-old woman with a past medical history of hypertension "
            "presented with nausea. Computed tomography (CT) demonstrated a "
            "cystic lesion near the pancreas. Laboratory tests showed elevated "
            "serum lipase at 850 U/L (reference range 10-140 U/L). The patient "
            "was diagnosed with pancreatitis based on imaging. The patient was "
            "treated with intravenous fluids. The patient was discharged home on day 4."
        )
        graph = _build(text)
        relations = {edge.relation for edge in graph.edges}

        self.assertTrue({
            "HAS_HISTORY", "HAS_SYMPTOM", "UNDERWENT_EXAM", "HAS_RESULT",
            "REVEALS", "LOCATED_IN", "DIAGNOSED_WITH", "TREATED_WITH",
            "HAS_OUTCOME", "SUPPORTS",
        }.issubset(relations))

    def test_all_edges_contain_auditable_attributes(self):
        graph = _build("A 44-year-old woman presented with nausea.")
        edge = graph.edges[0]
        self.assertEqual(edge.relation, "HAS_SYMPTOM")
        self.assertTrue(edge.attributes["evidence_text"])
        self.assertEqual(edge.attributes["trigger"], "presented with")
        self.assertIsInstance(edge.attributes["char_start"], int)
        self.assertIsInstance(edge.attributes["char_end"], int)

    def test_creates_revision_between_suspected_and_confirmed_diagnoses(self):
        text = (
            "The findings were suggesting the diagnosis of a mucinous neoplasm. "
            "Final evaluation was consistent with gastric duplication cyst."
        )
        graph = _build(text)
        revisions = [edge for edge in graph.edges if edge.relation == "REVISES"]
        self.assertEqual(len(revisions), 1)

    def test_does_not_duplicate_same_relation(self):
        graph = _build("A 44-year-old woman presented with nausea and nausea.")
        symptom_edges = [edge for edge in graph.edges if edge.relation == "HAS_SYMPTOM"]
        self.assertEqual(len(symptom_edges), 1)


if __name__ == "__main__":
    unittest.main()
