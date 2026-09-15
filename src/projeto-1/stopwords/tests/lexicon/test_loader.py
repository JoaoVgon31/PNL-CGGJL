import unittest

from stopwords.lexicon.loader import load_list


class LoadListTests(unittest.TestCase):
    def test_loads_nltk_list(self):
        words = load_list("nltk_stopwords")
        self.assertIn("no", words)
        self.assertIn("of", words)
        self.assertNotIn("without", words)  # nltk's list lacks this one

    def test_loads_spacy_list(self):
        words = load_list("spacy_stopwords")
        self.assertIn("without", words)
        self.assertIn("never", words)

    def test_loads_protection_list(self):
        words = load_list("protection_list")
        self.assertIn("no", words)
        self.assertIn("denies", words)

    def test_custom_clinical_excludes_protected_terms_present_in_public_lists(self):
        nltk_words = load_list("nltk_stopwords")
        spacy_words = load_list("spacy_stopwords")
        protection = load_list("protection_list")
        custom = load_list("custom_clinical")

        self.assertEqual(custom, (nltk_words | spacy_words) - protection)


if __name__ == "__main__":
    unittest.main()
