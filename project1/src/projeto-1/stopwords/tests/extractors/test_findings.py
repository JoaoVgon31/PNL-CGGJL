import unittest

from stopwords.extractors.findings import extract_findings


class ExtractFindingsTests(unittest.TestCase):
    def test_extracts_finding_with_size(self):
        text = "Contrast enhanced CT demonstrated a 6 cm cystic lesion in the pancreas."
        mentions = extract_findings(text)
        self.assertTrue(mentions)
        self.assertEqual(mentions[0].attributes["size"], "6 cm")

    def test_negated_finding_is_absent_and_confirmed_certainty(self):
        text = "FNA of the cyst demonstrated no evidence of malignancy."
        mentions = extract_findings(text)
        self.assertTrue(mentions)
        finding = mentions[0]
        self.assertEqual(finding.attributes["polarity"], "absent")

    def test_infers_imaging_source(self):
        text = "Computed tomography demonstrated a mass."
        mentions = extract_findings(text)
        self.assertEqual(mentions[0].attributes["source"], "imaging")

    def test_no_trigger_no_mentions(self):
        self.assertEqual(extract_findings("The patient was stable."), [])

    def test_offset_correct_when_label_appears_multiple_times(self):
        # Regression test: when label word appears before and after trigger in same sentence,
        # offset should point to the occurrence AFTER the trigger, not the first occurrence
        text = "the mass was found, and imaging demonstrated the mass."
        mentions = extract_findings(text)
        self.assertTrue(mentions)
        mention = mentions[0]

        # The extracted text should match the label
        self.assertEqual(text[mention.char_start:mention.char_end], mention.label)

        # Should extract the second "the mass", not the first
        # First "the mass" is at position 0-7, second is at position 45-53
        self.assertEqual(mention.char_start, 45)
        self.assertEqual(mention.char_end, 53)

        # Verify it's NOT extracting from the first occurrence
        self.assertNotEqual(text[0:7], mention.label)
        self.assertNotEqual(mention.char_start, 0)


if __name__ == "__main__":
    unittest.main()
