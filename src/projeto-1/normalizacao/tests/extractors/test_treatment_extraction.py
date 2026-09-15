"""Testes da extração de medicamentos e tratamentos."""


import unittest
from decimal import Decimal


from normalizacao.core.graph import GraphBuilder
from normalizacao.extractors.treatments import extract_medications, extract_treatments


class MedicationExtractionTests(unittest.TestCase):
    def test_extracts_dose_frequency_and_route(self):
        text = "The patient received oral oseltamivir 75 mg twice daily."
        graph = GraphBuilder("PMC5137649_01", text)
        node = extract_medications(text, graph)[0].node
        self.assertEqual(node.label, "oseltamivir")
        self.assertEqual(node.attributes["dose_value"], Decimal("75"))
        self.assertEqual(node.attributes["dose_unit"], "mg")
        self.assertEqual(node.attributes["frequency"], "twice daily")
        self.assertEqual(node.attributes["route"], "oral")

    def test_keeps_dose_changes_separate(self):
        text = "Prednisone 25 mg was given. The dose was reduced to prednisone 15 mg."
        graph = GraphBuilder("PMC5137649_01", text)
        results = extract_medications(text, graph)
        self.assertEqual(len(results), 2)
        self.assertNotEqual(results[0].node.node_id, results[1].node.node_id)
        self.assertEqual(results[1].node.attributes["dose_change"], "reduced")


class TreatmentExtractionTests(unittest.TestCase):
    def test_extracts_planned_surgery(self):
        text = "A laparoscopic distal pancreatectomy was planned."
        graph = GraphBuilder("PMC5137649_01", text)
        node = extract_treatments(text, graph)[0].node
        self.assertEqual(node.label, "laparoscopic distal pancreatectomy")
        self.assertEqual(node.attributes["type"], "surgery")
        self.assertEqual(node.attributes["status"], "planned")

    def test_extracts_supportive_treatments(self):
        text = "The patient was treated with intravenous fluids and analgesia."
        graph = GraphBuilder("PMC5137649_01", text)
        results = extract_treatments(text, graph)
        self.assertEqual([item.node.label for item in results], ["intravenous fluids", "analgesia"])
        self.assertTrue(all(item.node.attributes["type"] == "supportive" for item in results))


if __name__ == "__main__":
    unittest.main()
