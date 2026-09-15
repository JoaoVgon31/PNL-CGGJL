"""Testes do construtor de grafos."""


import unittest



from normalizacao.core.graph import GraphBuilder


class GraphBuilderTests(unittest.TestCase):
    def setUp(self):
        self.builder = GraphBuilder(
            case_id="PMC5137649_01",
            case_text=(
                "Computed tomography (CT) was performed. "
                "Later, CT demonstrated a lesion."
            ),
        )

    def test_generates_ids_per_node_type(self):
        first_exam = self.builder.add_node("Exam", "CT")
        second_exam = self.builder.add_node(
            "Exam",
            "Magnetic Resonance Imaging",
        )
        symptom = self.builder.add_node(
            "Symptom",
            "Abdominal Pain",
        )

        self.assertEqual(first_exam.node_id, "E1")
        self.assertEqual(second_exam.node_id, "E2")
        self.assertEqual(symptom.node_id, "S1")

    def test_normalizes_node_label(self):
        exam = self.builder.add_node("Exam", "CT")

        self.assertEqual(
            exam.label,
            "computed tomography",
        )

    def test_preserves_patient_identifier_case(self):
        patient = self.builder.add_node(
            "Patient",
            "case PMC5137649_01",
        )

        self.assertEqual(
            patient.label,
            "case PMC5137649_01",
        )

    def test_generates_sequential_edge_ids(self):
        patient = self.builder.add_node(
            "Patient",
            "case PMC5137649_01",
        )
        exam = self.builder.add_node("Exam", "CT")
        symptom = self.builder.add_node(
            "Symptom",
            "abdominal pain",
        )

        first_edge = self.builder.add_edge(
            patient.node_id,
            exam.node_id,
            "UNDERWENT_EXAM",
        )
        second_edge = self.builder.add_edge(
            patient.node_id,
            symptom.node_id,
            "HAS_SYMPTOM",
        )

        self.assertEqual(first_edge.edge_id, "e1")
        self.assertEqual(second_edge.edge_id, "e2")

    def test_rejects_missing_source_node(self):
        exam = self.builder.add_node("Exam", "CT")

        with self.assertRaises(ValueError):
            self.builder.add_edge(
                "P99",
                exam.node_id,
                "UNDERWENT_EXAM",
            )

    def test_rejects_missing_target_node(self):
        patient = self.builder.add_node(
            "Patient",
            "case PMC5137649_01",
        )

        with self.assertRaises(ValueError):
            self.builder.add_edge(
                patient.node_id,
                "E99",
                "UNDERWENT_EXAM",
            )

    def test_produces_rows_in_contract_format(self):
        exam = self.builder.add_node(
            "Exam",
            "CT",
            {"modality": "imaging"},
        )

        self.assertEqual(
            self.builder.node_rows(),
            [
                {
                    "case_id": "PMC5137649_01",
                    "node_id": exam.node_id,
                    "type": "Exam",
                    "label": "computed tomography",
                    "attributes": "modality=imaging",
                }
            ],
        )

    def test_rejects_invalid_case_id(self):
        with self.assertRaises(ValueError):
            GraphBuilder(
                case_id="invalid",
                case_text="Some text.",
            )

class GraphDeduplicationTests(unittest.TestCase):
    def setUp(self):
        self.builder = GraphBuilder(
            case_id="PMC5137649_01",
            case_text=(
                "Computed tomography (CT) was performed. "
                "Later, CT demonstrated a lesion."
            ),
        )

    def test_merges_equivalent_exam_labels(self):
        first = self.builder.add_node("Exam", "CT")
        second = self.builder.add_node(
            "Exam",
            "Computed Tomography",
        )

        self.assertIs(first, second)
        self.assertEqual(first.node_id, "E1")
        self.assertEqual(len(self.builder.nodes), 1)

    def test_merges_missing_attributes(self):
        first = self.builder.add_node(
            "Exam",
            "CT",
            {"abbreviation": "CT"},
        )
        second = self.builder.add_node(
            "Exam",
            "Computed Tomography",
            {"contrast": True},
        )

        self.assertIs(first, second)
        self.assertEqual(
            first.attributes,
            {
                "abbreviation": "CT",
                "contrast": True,
            },
        )

    def test_does_not_merge_different_medication_doses(self):
        first = self.builder.add_node(
            "Medication",
            "Prednisone",
            {
                "dose_value": 25,
                "dose_unit": "mg",
            },
        )
        second = self.builder.add_node(
            "Medication",
            "prednisone",
            {
                "dose_value": 15,
                "dose_unit": "mg",
            },
        )

        self.assertNotEqual(first.node_id, second.node_id)
        self.assertEqual(len(self.builder.nodes), 2)

    def test_can_disable_deduplication(self):
        first = self.builder.add_node(
            "Exam",
            "CT",
            deduplicate=False,
        )
        second = self.builder.add_node(
            "Exam",
            "CT",
            deduplicate=False,
        )

        self.assertNotEqual(first.node_id, second.node_id)

    def test_reports_normalization_impact(self):
        self.builder.add_node("Exam", "CT")
        self.builder.add_node(
            "Exam",
            "Computed Tomography",
        )

        impact = self.builder.normalization_impact()

        self.assertEqual(impact.mentions_processed, 2)
        self.assertEqual(impact.raw_nodes, 2)
        self.assertEqual(impact.normalized_nodes, 1)
        self.assertEqual(impact.nodes_merged, 1)
        self.assertEqual(impact.labels_changed, 2)

    def test_does_not_merge_conflicting_identity_attributes(self):
        first = self.builder.add_node(
            "Exam",
            "CT",
            {"contrast": True},
        )
        second = self.builder.add_node(
            "Exam",
            "Computed Tomography",
            {"contrast": False},
        )

        self.assertNotEqual(first.node_id, second.node_id)
        self.assertEqual(len(self.builder.nodes), 2)

if __name__ == "__main__":
    unittest.main()