"""Testes das regras básicas de normalização."""


import unittest



from normalizacao.normalizers.text import normalize_label


class NormalizeLabelTests(unittest.TestCase):
    def test_applies_case_folding(self):
        self.assertEqual(
            normalize_label("Computed Tomography"),
            "computed tomography",
        )

    def test_collapses_repeated_whitespace(self):
        self.assertEqual(
            normalize_label("computed   tomography"),
            "computed tomography",
        )

    def test_removes_boundary_punctuation(self):
        self.assertEqual(
            normalize_label('"hypertension,"'),
            "hypertension",
        )

    def test_preserves_internal_hyphen(self):
        self.assertEqual(
            normalize_label("C-reactive protein"),
            "c-reactive protein",
        )

    def test_normalizes_unicode_compatibility_characters(self):
        # A ligadura Unicode "ﬁ" deve se tornar as letras comuns "fi".
        self.assertEqual(
            normalize_label("ﬁnding"),
            "finding",
        )

    def test_empty_text_remains_empty(self):
        self.assertEqual(normalize_label("   "), "")

    def test_rejects_non_string_input(self):
        with self.assertRaises(TypeError):
            normalize_label(123)


    def test_restores_ca_19_9_canonical_case(self):
        self.assertEqual(
            normalize_label("ca 19-9"),
            "CA 19-9",
        )

    def test_normalizes_ca_19_9_spacing_and_dash(self):
        self.assertEqual(
            normalize_label("CA19–9 level"),
            "CA 19-9 level",
        )

    def test_restores_her2_and_removes_variant_hyphen(self):
        self.assertEqual(
            normalize_label("HER-2-positive tumor"),
            "HER2-positive tumor",
        )

    def test_restores_ph_inside_label(self):
        self.assertEqual(
            normalize_label("SERUM PH"),
            "serum pH",
        )

    def test_restores_immunoglobulin_case(self):
        self.assertEqual(
            normalize_label("IGG and IGM"),
            "IgG and IgM",
        )

    def test_does_not_change_ca_by_itself(self):
        self.assertEqual(
            normalize_label("CA"),
            "ca",
        )

    def test_does_not_replace_inside_other_words(self):
        self.assertEqual(
            normalize_label("phase"),
            "phase",
        )


if __name__ == "__main__":
    unittest.main()