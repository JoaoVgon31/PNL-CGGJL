import unittest

from stopwords.core.graph import GraphBuilder
from stopwords.extractors.common import Mention, Sentence
from stopwords.extractors.relations import build_relations


def _sentence(text: str, index: int = 0) -> Sentence:
    return Sentence(text=text, start=0, end=len(text), index=index)


def _mention(node_type: str, label: str, attributes=None, sentence=None, trigger="trigger", hedged=False) -> Mention:
    return Mention(
        node_type=node_type, label=label, attributes=attributes or {},
        sentence=sentence or _sentence(f"{trigger} {label}"),
        trigger=trigger, char_start=0, char_end=len(label), hedged=hedged,
    )


class BuildRelationsTests(unittest.TestCase):
    def setUp(self):
        self.graph = GraphBuilder("PMC1234567_01")
        self.patient = self.graph.add_node("Patient", "patient")

    def test_direct_patient_relations(self):
        symptom_mention = _mention("Symptom", "pain")
        symptom_node = self.graph.add_node("Symptom", "pain")
        build_relations(self.graph, self.patient.node_id, {"Symptom": [(symptom_mention, symptom_node)]})
        relations = [edge.relation for edge in self.graph.edges]
        self.assertIn("HAS_SYMPTOM", relations)

    def test_has_result_links_exam_in_same_sentence(self):
        sentence = _sentence("underwent CEA testing level of 12,476.5", index=0)
        exam_mention = _mention("Exam", "CEA testing", sentence=sentence)
        exam_node = self.graph.add_node("Exam", "CEA testing")
        result_mention = _mention("ExamResult", "12476.5", sentence=sentence)
        result_node = self.graph.add_node("ExamResult", "12476.5")

        build_relations(self.graph, self.patient.node_id, {
            "Exam": [(exam_mention, exam_node)],
            "ExamResult": [(result_mention, result_node)],
        })
        has_result_edges = [e for e in self.graph.edges if e.relation == "HAS_RESULT"]
        self.assertEqual(len(has_result_edges), 1)
        self.assertEqual(has_result_edges[0].source_id, exam_node.node_id)

    def test_finding_falls_back_to_patient_without_exam(self):
        finding_mention = _mention("Finding", "mass")
        finding_node = self.graph.add_node("Finding", "mass")
        build_relations(self.graph, self.patient.node_id, {"Finding": [(finding_mention, finding_node)]})
        has_finding_edges = [e for e in self.graph.edges if e.relation == "HAS_FINDING"]
        self.assertEqual(len(has_finding_edges), 1)
        self.assertEqual(has_finding_edges[0].source_id, self.patient.node_id)

    def test_revises_links_more_certain_later_diagnosis_to_earlier(self):
        earlier = _mention(
            "Diagnosis", "mucinous cystic neoplasm",
            attributes={"certainty": "suspected"}, sentence=_sentence("suggesting X", index=0),
        )
        earlier_node = self.graph.add_node("Diagnosis", "mucinous cystic neoplasm")
        later = _mention(
            "Diagnosis", "gastric duplication cyst",
            attributes={"certainty": "confirmed"}, sentence=_sentence("revealed Y", index=3),
        )
        later_node = self.graph.add_node("Diagnosis", "gastric duplication cyst")

        build_relations(self.graph, self.patient.node_id, {
            "Diagnosis": [(earlier, earlier_node), (later, later_node)],
        })
        revises_edges = [e for e in self.graph.edges if e.relation == "REVISES"]
        self.assertEqual(len(revises_edges), 1)
        self.assertEqual(revises_edges[0].source_id, later_node.node_id)
        self.assertEqual(revises_edges[0].target_id, earlier_node.node_id)


if __name__ == "__main__":
    unittest.main()
