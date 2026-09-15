"""Testes das decisões de fronteira e dos offsets."""

import sys
import unittest
from pathlib import Path


SOURCE = Path(__file__).parents[1]
sys.path.insert(0, str(SOURCE))

from tokenizers import (  # noqa: E402
    ClinicalRegexTokenizer,
    TreebankTokenizer,
    WhitespaceTokenizer,
)


class ClinicalRegexTokenizerTests(unittest.TestCase):
    def setUp(self):
        self.tokenizer = ClinicalRegexTokenizer()

    def assert_tokens(self, text, expected):
        tokens = self.tokenizer.tokenize(text)
        self.assertEqual([token.text for token in tokens], expected)
        for token in tokens:
            self.assertEqual(text[token.start:token.end], token.text)

    def test_issue_examples(self):
        examples = {
            "12,476.5ng/ml": ["12,476.5", "ng/ml"],
            "6cm x 9cm": ["6", "cm", "x", "9", "cm"],
            "6iu/ml": ["6", "iu/ml"],
            "EUS-FNA": ["EUS-FNA"],
            "contrast-enhanced": ["contrast-enhanced"],
            "CA 19-9": ["CA", "19-9"],
            "(Fig 1)": ["(Fig 1)"],
            "10-140 U/L": ["10-140", "U/L"],
            "body/tail": ["body/tail"],
        }
        for text, expected in examples.items():
            with self.subTest(text=text):
                self.assert_tokens(text, expected)

    def test_classifies_special_tokens(self):
        tokens = self.tokenizer.tokenize("(Figs 3-5) 9.5cm EUS-FNA")
        self.assertEqual(
            [token.kind for token in tokens],
            ["FIGURE_REF", "NUMBER", "UNIT", "WORD"],
        )

    def test_does_not_silently_skip_unicode(self):
        text = "10 µg/µL – normal"
        tokens = self.tokenizer.tokenize(text)
        for token in tokens:
            self.assertEqual(text[token.start:token.end], token.text)
        reconstructed_nonspace = "".join(token.text for token in tokens).replace(" ", "")
        self.assertEqual(reconstructed_nonspace, text.replace(" ", ""))

    def test_rejects_non_string(self):
        with self.assertRaises(TypeError):
            self.tokenizer.tokenize(None)


class BaselineTests(unittest.TestCase):
    def test_whitespace_baseline_exposes_failure(self):
        tokens = WhitespaceTokenizer().tokenize("level 12,476.5ng/ml (Fig 1)")
        self.assertEqual(
            [token.text for token in tokens],
            ["level", "12,476.5ng/ml", "(Fig", "1)"],
        )

    def test_treebank_preserves_offsets_without_corpus_download(self):
        try:
            tokens = TreebankTokenizer().tokenize("A 0.016 ng/mL result.")
        except RuntimeError as error:
            self.skipTest(str(error))
        text = "A 0.016 ng/mL result."
        self.assertEqual([token.text for token in tokens], ["A", "0.016", "ng/mL", "result", "."])
        self.assertTrue(all(text[token.start:token.end] == token.text for token in tokens))


if __name__ == "__main__":
    unittest.main()
