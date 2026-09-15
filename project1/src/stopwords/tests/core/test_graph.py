import unittest

from stopwords.core.graph import GraphBuilder


class GraphBuilderTests(unittest.TestCase):
    def setUp(self):
        self.graph = GraphBuilder("PMC1234567_01")

    def test_assigns_sequential_ids_per_type(self):
        first = self.graph.add_node("Symptom", "abdominal pain")
        second = self.graph.add_node("Symptom", "nausea")
        self.assertEqual(first.node_id, "S1")
        self.assertEqual(second.node_id, "S2")

    def test_dedupes_same_type_and_label(self):
        first = self.graph.add_node("Symptom", "abdominal pain", {"polarity": "present"})
        second = self.graph.add_node("Symptom", "  abdominal   pain ", {"duration": "3 days"})
        self.assertIs(first, second)
        self.assertEqual(first.attributes, {"polarity": "present", "duration": "3 days"})

    def test_does_not_overwrite_existing_attribute(self):
        first = self.graph.add_node("Symptom", "pain", {"polarity": "present"})
        self.graph.add_node("Symptom", "pain", {"polarity": "absent"})
        self.assertEqual(first.attributes["polarity"], "present")

    def test_add_edge_between_existing_nodes(self):
        patient = self.graph.add_node("Patient", "patient")
        symptom = self.graph.add_node("Symptom", "pain")
        edge = self.graph.add_edge(patient.node_id, symptom.node_id, "HAS_SYMPTOM")
        self.assertEqual(edge.edge_id, "e1")

    def test_add_edge_rejects_unknown_endpoint(self):
        patient = self.graph.add_node("Patient", "patient")
        with self.assertRaises(ValueError):
            self.graph.add_edge(patient.node_id, "S99", "HAS_SYMPTOM")

    def test_rejects_invalid_case_id(self):
        with self.assertRaises(ValueError):
            GraphBuilder("not-a-case-id")

    def test_node_rows_and_edge_rows(self):
        patient = self.graph.add_node("Patient", "patient")
        symptom = self.graph.add_node("Symptom", "pain")
        self.graph.add_edge(patient.node_id, symptom.node_id, "HAS_SYMPTOM")
        self.assertEqual(len(self.graph.node_rows()), 2)
        self.assertEqual(len(self.graph.edge_rows()), 1)


if __name__ == "__main__":
    unittest.main()
