"""Testes da camada de normalização por caso."""


import unittest
from decimal import Decimal



from normalizacao.normalizers.case import CaseNormalizer


class CaseNormalizerTests(unittest.TestCase):
    def setUp(self):
        self.case_text = (
            "Computed tomography (CT) was performed. "
            "Later, CT demonstrated a cystic lesion. "
            "The CA 19-9 level was measured."
        )
        self.normalizer = CaseNormalizer(self.case_text)

    def test_discovers_case_acronyms(self):
        self.assertEqual(
            self.normalizer.acronym_definitions,
            {"CT": "Computed tomography"},
        )

    def test_different_surface_forms_converge(self):
        from_acronym = self.normalizer.normalize_entity_label("CT")
        from_long_form = self.normalizer.normalize_entity_label(
            "Computed Tomography,"
        )

        self.assertEqual(from_acronym, "computed tomography")
        self.assertEqual(from_long_form, "computed tomography")

    def test_preserves_sensitive_term_without_definition(self):
        self.assertEqual(
            self.normalizer.normalize_entity_label("CA 19-9"),
            "CA 19-9",
        )

    def test_acronyms_do_not_leak_between_cases(self):
        another_case = CaseNormalizer(
            "Magnetic resonance imaging was performed."
        )

        self.assertEqual(
            another_case.acronym_definitions,
            {},
        )
        self.assertEqual(
            another_case.normalize_entity_label("CT"),
            "ct",
        )

    def test_returns_copy_of_acronym_dictionary(self):
        definitions = self.normalizer.acronym_definitions
        definitions["MRI"] = "magnetic resonance imaging"

        self.assertNotIn(
            "MRI",
            self.normalizer.acronym_definitions,
        )

    def test_delegates_measurement_normalization(self):
        measurement = self.normalizer.normalize_measurement(
            "12,476.5ng/ml"
        )

        self.assertEqual(
            measurement.value,
            Decimal("12476.5"),
        )
        self.assertEqual(measurement.unit, "ng/mL")
        self.assertEqual(
            measurement.raw_text,
            "12,476.5ng/ml",
        )

    def test_delegates_reference_range_normalization(self):
        reference = self.normalizer.normalize_reference_range(
            "normal range, 0-0.04 ng/mL"
        )

        self.assertEqual(reference.low, Decimal("0"))
        self.assertEqual(reference.high, Decimal("0.04"))
        self.assertEqual(reference.unit, "ng/mL")

    def test_rejects_invalid_case_text(self):
        with self.assertRaises(TypeError):
            CaseNormalizer(None)


if __name__ == "__main__":
    unittest.main()