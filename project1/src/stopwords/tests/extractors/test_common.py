import unittest

from stopwords.extractors.common import detect_certainty, detect_polarity, is_hedged, split_sentences


class SplitSentencesTests(unittest.TestCase):
    def test_splits_on_terminal_punctuation(self):
        sentences = split_sentences("First one. Second one! Third one?")
        self.assertEqual([s.text for s in sentences], ["First one", " Second one", " Third one"])

    def test_indices_and_offsets_are_correct(self):
        text = "First. Second."
        sentences = split_sentences(text)
        self.assertEqual(sentences[0].index, 0)
        self.assertEqual(sentences[1].index, 1)
        self.assertEqual(text[sentences[1].start:sentences[1].end], sentences[1].text)

    def test_handles_no_terminal_punctuation(self):
        sentences = split_sentences("no punctuation here")
        self.assertEqual(len(sentences), 1)

    def test_preserves_decimal_points_in_measurements(self):
        text = "The mass measured 3.5 cm in the largest dimension."
        sentences = split_sentences(text)
        self.assertEqual(len(sentences), 1)
        self.assertEqual(sentences[0].text, "The mass measured 3.5 cm in the largest dimension")


class PolarityAndCertaintyTests(unittest.TestCase):
    def test_detects_negation(self):
        self.assertEqual(detect_polarity("FNA demonstrated no evidence of malignancy"), "absent")

    def test_detects_presence_by_default(self):
        self.assertEqual(detect_polarity("demonstrated a cystic lesion"), "present")

    def test_detects_without(self):
        self.assertEqual(detect_polarity("presented without fever"), "absent")

    def test_detects_denies(self):
        self.assertEqual(detect_polarity("patient denies chest pain"), "absent")

    def test_does_not_false_positive_on_cannot(self):
        self.assertEqual(detect_polarity("cannot obtain consent"), "present")

    def test_detects_suspected_hedge(self):
        self.assertEqual(detect_certainty("suggesting the diagnosis of a cystic neoplasm"), "suspected")

    def test_detects_probable_hedge(self):
        self.assertEqual(detect_certainty("consistent with a gastric duplication cyst"), "probable")

    def test_defaults_to_confirmed(self):
        self.assertEqual(detect_certainty("was diagnosed with PCH"), "confirmed")

    def test_is_hedged_matches_certainty(self):
        self.assertTrue(is_hedged("suggesting a diagnosis"))
        self.assertFalse(is_hedged("was diagnosed with PCH"))


if __name__ == "__main__":
    unittest.main()
