"""Testes da extração de achados e localizações."""


import unittest


from normalizacao.extractors.findings import extract_findings
from normalizacao.core.graph import GraphBuilder


class FindingExtractionTests(unittest.TestCase):
    def test_extracts_imaging_finding_size_and_site(self):
        text = "CT demonstrated a 6 cm cystic lesion near the pancreas."
        graph = GraphBuilder("PMC5137649_01", text)

        result = extract_findings(text, graph)[0]

        self.assertEqual(result.entity.node.label, "cystic lesion")
        self.assertEqual(result.entity.node.attributes["source"], "imaging")
        self.assertEqual(result.entity.node.attributes["size"], "6 cm")
        self.assertIn("pancreas", [node.label for node in result.anatomical_sites])

    def test_marks_excluded_finding_as_absent(self):
        text = "FNA revealed no evidence of malignancy."
        graph = GraphBuilder("PMC5137649_01", text)

        result = extract_findings(text, graph)[0]
        self.assertEqual(result.entity.node.label, "malignancy")
        self.assertEqual(result.entity.node.attributes["polarity"], "absent")
        self.assertEqual(result.entity.node.attributes["source"], "pathology")

    def test_extracts_physical_examination_finding(self):
        text = "Physical examination revealed epigastric tenderness."
        graph = GraphBuilder("PMC5137649_01", text)

        result = extract_findings(text, graph)[0]
        self.assertEqual(result.entity.node.label, "epigastric tenderness")
        self.assertEqual(result.entity.node.attributes["source"], "physical_exam")

    def test_requires_finding_context(self):
        text = "The article discussed the concept of a mass."
        graph = GraphBuilder("PMC5137649_01", text)
        self.assertEqual(extract_findings(text, graph), [])


if __name__ == "__main__":
    unittest.main()
