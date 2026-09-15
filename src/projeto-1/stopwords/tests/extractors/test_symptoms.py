import unittest

from stopwords.extractors.symptoms import extract_symptoms


class ExtractSymptomsTests(unittest.TestCase):
    def test_extracts_symptom_after_presented_with(self):
        text = "A 44-year-old woman presented with abdominal pain associated with nausea."
        mentions = extract_symptoms(text)
        labels = [m.label for m in mentions]
        self.assertIn("abdominal pain", labels)
        self.assertIn("nausea", labels)

    def test_extracts_duration_prefix(self):
        text = "She presented with a 3-day history of right flank pain."
        mentions = extract_symptoms(text)
        self.assertTrue(any(m.attributes.get("duration") == "3 days" for m in mentions))

    def test_negated_symptom_has_absent_polarity(self):
        text = "He denies fever and night sweating."
        mentions = extract_symptoms(text)
        self.assertTrue(mentions)
        for mention in mentions:
            self.assertEqual(mention.attributes["polarity"], "absent")

    def test_no_trigger_produces_no_mentions(self):
        text = "The patient was stable overnight."
        self.assertEqual(extract_symptoms(text), [])

    def test_all_mentions_are_symptom_type(self):
        text = "presented with pain"
        for mention in extract_symptoms(text):
            self.assertEqual(mention.node_type, "Symptom")

    def test_char_offsets_point_to_correct_occurrence(self):
        """Regression: char_start must point at the SECOND 'pain', not the first."""
        text = "Patient with pain history presented with pain."
        mentions = extract_symptoms(text)
        # Should extract only the "pain" after "presented with"
        self.assertEqual(len(mentions), 1)
        pain_mention = mentions[0]
        self.assertEqual(pain_mention.label, "pain")
        # The char_start should point at the second occurrence (after "presented with")
        extracted_text = text[pain_mention.char_start:pain_mention.char_end]
        self.assertEqual(extracted_text, "pain")
        # Verify it's the SECOND "pain" by checking position
        first_pain_pos = text.find("pain")
        self.assertGreater(pain_mention.char_start, first_pain_pos)

    def test_multiple_triggers_in_same_sentence(self):
        """Regression: multiple triggers in one sentence should produce separate mentions with correct polarity."""
        text = "He presented with fever, denies chills."
        mentions = extract_symptoms(text)
        # Should produce exactly two mentions
        self.assertEqual(len(mentions), 2)
        labels = [m.label for m in mentions]
        self.assertIn("fever", labels)
        self.assertIn("chills", labels)
        # Check polarities
        fever_mention = next(m for m in mentions if m.label == "fever")
        chills_mention = next(m for m in mentions if m.label == "chills")
        self.assertEqual(fever_mention.attributes["polarity"], "present")
        self.assertEqual(chills_mention.attributes["polarity"], "absent")
        # Ensure no label contains the word "denies"
        for mention in mentions:
            self.assertNotIn("denies", mention.label.lower())


if __name__ == "__main__":
    unittest.main()
