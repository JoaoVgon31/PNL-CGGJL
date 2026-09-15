import unittest

from stopwords.experiment.conditions import WORDLISTS, Condition


class ConditionsTests(unittest.TestCase):
    def test_has_four_conditions(self):
        self.assertEqual(
            {c.name for c in Condition},
            {"BASELINE", "NAIVE_UNPROTECTED", "GUARDED_GLOBAL", "GUARDED_LABEL"},
        )

    def test_wordlists_match_lexicon_file_names(self):
        self.assertEqual(WORDLISTS, ("nltk_stopwords", "spacy_stopwords", "custom_clinical"))


if __name__ == "__main__":
    unittest.main()
