import unittest

from stopwords.lexicon.masking import mask_text


class MaskTextTests(unittest.TestCase):
    def test_masks_matching_words_preserving_length(self):
        text = "no evidence of malignancy"
        result = mask_text(text, frozenset({"no", "of"}), frozenset())
        self.assertEqual(len(result), len(text))
        self.assertEqual(result, "   evidence    malignancy")

    def test_protected_words_are_never_masked(self):
        text = "no evidence of malignancy"
        result = mask_text(text, frozenset({"no", "of"}), frozenset({"no"}))
        self.assertIn("no", result)
        self.assertNotIn(" of ", result.replace("  ", " "))  # 'of' still masked

    def test_does_not_mask_substrings_inside_other_words(self):
        text = "nostril and often"
        result = mask_text(text, frozenset({"no"}), frozenset())
        self.assertEqual(result, text)  # 'no' is not a standalone word here

    def test_case_insensitive(self):
        text = "No evidence"
        result = mask_text(text, frozenset({"no"}), frozenset())
        self.assertEqual(result, "   evidence")

    def test_empty_remove_words_returns_original(self):
        text = "no evidence of malignancy"
        self.assertEqual(mask_text(text, frozenset(), frozenset()), text)

    def test_offsets_of_untouched_words_stay_valid(self):
        text = "no evidence of malignancy"
        result = mask_text(text, frozenset({"no", "of"}), frozenset())
        start = text.index("malignancy")
        self.assertEqual(result[start:start + len("malignancy")], "malignancy")


if __name__ == "__main__":
    unittest.main()
