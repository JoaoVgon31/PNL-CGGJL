import unittest

from stopwords.extractors.history import extract_history


class ExtractHistoryTests(unittest.TestCase):
    def test_extracts_past_medical_history(self):
        text = "A 65-year-old male with a past medical history significant for hypertension, asthma."
        mentions = extract_history(text)
        labels = [m.label for m in mentions]
        self.assertIn("hypertension", labels)
        self.assertIn("asthma", labels)
        for mention in mentions:
            self.assertEqual(mention.attributes["subject"], "patient")

    def test_does_not_trigger_on_symptom_duration_phrase(self):
        text = "She presented with a 3-day history of abdominal pain."
        self.assertEqual(extract_history(text), [])

    def test_detects_family_subject(self):
        text = "Family history of breast cancer in her mother."
        mentions = extract_history(text)
        self.assertTrue(mentions)
        self.assertEqual(mentions[0].attributes["subject"], "family")

    def test_infers_surgery_category(self):
        text = "History of mitral valve replacement."
        mentions = extract_history(text)
        self.assertTrue(any(m.attributes["category"] == "surgery" for m in mentions))

    def test_defaults_to_condition_category(self):
        text = "History of hypertension."
        mentions = extract_history(text)
        self.assertTrue(any(m.attributes["category"] == "condition" for m in mentions))

    def test_handles_multiple_triggers_with_per_clause_subject(self):
        """Regression test: subject should be scoped per clause, not sentence-wide.
        Also verifies that 'of' is properly consumed by the trigger and not leaked into labels.
        """
        text = "Past medical history of hypertension and past medical history of diabetes in her mother."
        mentions = extract_history(text)
        self.assertEqual(len(mentions), 2)

        # First mention: patient's hypertension (no "of" prefix, no family terms in clause)
        self.assertEqual(mentions[0].label, "hypertension")
        self.assertEqual(mentions[0].attributes["subject"], "patient")

        # Second mention: family history of diabetes (no "of" prefix, "mother" is in clause)
        self.assertEqual(mentions[1].label, "diabetes in her mother")
        self.assertEqual(mentions[1].attributes["subject"], "family")


if __name__ == "__main__":
    unittest.main()
