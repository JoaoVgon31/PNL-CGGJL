"""Testes da extração de exames e resultados."""


import unittest
from decimal import Decimal


from normalizacao.extractors.exams import extract_exam_results, extract_exams
from normalizacao.core.graph import GraphBuilder


class ExamExtractionTests(unittest.TestCase):
    def test_extracts_and_deduplicates_ct(self):
        text = "Computed tomography (CT) was performed. A repeat CT scan was performed."
        graph = GraphBuilder("PMC5137649_01", text)

        extracted = extract_exams(text, graph)

        self.assertGreaterEqual(len(extracted), 2)
        self.assertEqual(len(graph.nodes), 1)
        self.assertEqual(graph.nodes[0].label, "computed tomography")
        self.assertEqual(graph.nodes[0].attributes["modality"], "imaging")

    def test_ignores_exam_word_without_diagnostic_context(self):
        text = "The CT company published a report."
        graph = GraphBuilder("PMC5137649_01", text)
        self.assertEqual(extract_exams(text, graph), [])

    def test_builds_exam_and_result_with_reference_range(self):
        text = "Laboratory tests showed elevated serum lipase at 850 U/L (reference range 10-140 U/L)."
        graph = GraphBuilder("PMC5137649_01", text)

        result = extract_exam_results(text, graph)[0]

        self.assertEqual(result.exam_node.type, "Exam")
        self.assertEqual(result.exam_node.label, "serum lipase")
        self.assertEqual(result.node.type, "ExamResult")
        self.assertEqual(result.node.attributes["value"], Decimal("850"))
        self.assertEqual(result.node.attributes["unit"], "U/L")
        self.assertEqual(result.node.attributes["reference_range_low"], Decimal("10"))
        self.assertEqual(result.node.attributes["interpretation"], "elevated")

    def test_keeps_repeated_results_as_distinct_nodes(self):
        text = "Troponin was 5 ng/mL. Later, troponin was 5 ng/mL."
        graph = GraphBuilder("PMC5137649_01", text)

        results = extract_exam_results(text, graph)

        self.assertEqual(len(results), 2)
        self.assertNotEqual(results[0].node.node_id, results[1].node.node_id)
        self.assertIs(results[0].exam_node, results[1].exam_node)


if __name__ == "__main__":
    unittest.main()
