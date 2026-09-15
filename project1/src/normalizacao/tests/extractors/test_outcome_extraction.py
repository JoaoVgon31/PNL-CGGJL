"""Testes da extração de desfechos."""


import unittest


from normalizacao.core.graph import GraphBuilder
from normalizacao.extractors.outcomes import extract_outcomes


class OutcomeExtractionTests(unittest.TestCase):
    def test_extracts_discharge_and_length_of_stay(self):
        text = "The patient was discharged home on postoperative day 4."
        graph = GraphBuilder("PMC5137649_01", text)
        node = extract_outcomes(text, graph)[0].node
        self.assertEqual(node.attributes["type"], "discharge")
        self.assertEqual(node.attributes["timing"], "postoperative day 4")
        self.assertEqual(node.attributes["length_of_stay"], "4 days")

    def test_extracts_death_after_improvement(self):
        text = "The patient improved but later expired."
        graph = GraphBuilder("PMC5137649_01", text)
        results = extract_outcomes(text, graph)
        self.assertEqual([item.node.attributes["type"] for item in results], ["improvement", "death"])

    def test_marks_absent_recurrence(self):
        text = "Follow-up showed no evidence of recurrence."
        graph = GraphBuilder("PMC5137649_01", text)
        node = extract_outcomes(text, graph)[0].node
        self.assertEqual(node.attributes["type"], "recurrence")
        self.assertEqual(node.attributes["polarity"], "absent")

    def test_extracts_follow_up_duration(self):
        text = "At 24 months of follow-up, there was complete resolution of symptoms."
        graph = GraphBuilder("PMC5137649_01", text)
        node = extract_outcomes(text, graph)[0].node
        self.assertEqual(node.attributes["follow_up_duration"], "24 months")


if __name__ == "__main__":
    unittest.main()
