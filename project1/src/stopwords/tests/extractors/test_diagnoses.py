import unittest

from stopwords.extractors.diagnoses import extract_diagnoses


class ExtractDiagnosesTests(unittest.TestCase):
    def test_extracts_confirmed_diagnosis(self):
        text = "She was diagnosed with PCH after having positive Donath-Landsteiner test."
        mentions = extract_diagnoses(text)
        self.assertTrue(mentions)
        self.assertEqual(mentions[0].attributes["certainty"], "confirmed")
        self.assertEqual(mentions[0].attributes["polarity"], "present")

    def test_extracts_hedged_diagnosis(self):
        text = "suggesting the diagnosis of a mucinous pancreatic cystic neoplasm."
        mentions = extract_diagnoses(text)
        self.assertTrue(mentions)
        self.assertEqual(mentions[0].attributes["certainty"], "suspected")
        self.assertTrue(mentions[0].hedged)

    def test_ruled_out_becomes_excluded(self):
        text = "Malignancy was ruled out."
        text_with_trigger = "consistent with malignancy which was ruled out."
        mentions = extract_diagnoses(text_with_trigger)
        self.assertTrue(mentions)
        self.assertEqual(mentions[0].attributes["certainty"], "excluded")
        self.assertEqual(mentions[0].attributes["polarity"], "absent")

    def test_differential_role(self):
        text = "The differential diagnosis of appendicitis was considered."
        mentions = extract_diagnoses(text)
        self.assertEqual(mentions[0].attributes["role"], "differential")


if __name__ == "__main__":
    unittest.main()
