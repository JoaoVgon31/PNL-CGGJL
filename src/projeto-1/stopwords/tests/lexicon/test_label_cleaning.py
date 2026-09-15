import unittest

from stopwords.lexicon.label_cleaning import clean_label


class CleanLabelTests(unittest.TestCase):
    def test_removes_listed_tokens(self):
        result = clean_label("the mass in the pancreas", frozenset({"the", "in"}), frozenset())
        self.assertEqual(result, "mass pancreas")

    def test_protected_tokens_survive(self):
        result = clean_label("history of type 2 diabetes", frozenset({"of"}), frozenset({"of"}))
        self.assertEqual(result, "history of type 2 diabetes")

    def test_never_returns_empty_label(self):
        result = clean_label("the", frozenset({"the"}), frozenset())
        self.assertEqual(result, "the")

    def test_no_removal_words_returns_original(self):
        label = "carcinoembryonic antigen"
        self.assertEqual(clean_label(label, frozenset(), frozenset()), label)


if __name__ == "__main__":
    unittest.main()
