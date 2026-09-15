"""Testes da normalização de números e unidades."""


import unittest
from decimal import Decimal



from normalizacao.normalizers.units import (
    normalize_number,
    normalize_unit,
    parse_measurement,
    parse_reference_range,
)


class NormalizeNumberTests(unittest.TestCase):
    def test_removes_thousands_separator(self):
        self.assertEqual(
            normalize_number("12,476.5"),
            Decimal("12476.5"),
        )

    def test_preserves_decimal_value(self):
        self.assertEqual(
            normalize_number("0.016"),
            Decimal("0.016"),
        )

    def test_rejects_malformed_number(self):
        with self.assertRaises(ValueError):
            normalize_number("12,34")


class NormalizeUnitTests(unittest.TestCase):
    def test_normalizes_known_unit_variants(self):
        examples = {
            "ng/ml": "ng/mL",
            "NG/ML": "ng/mL",
            "iu/ml": "IU/mL",
            "mg/dl": "mg/dL",
            "per microliter": "/µL",
            "/mm3": "/µL",
            "cells/mm³": "/µL",
        }

        for raw_unit, expected in examples.items():
            with self.subTest(raw_unit=raw_unit):
                self.assertEqual(
                    normalize_unit(raw_unit),
                    expected,
                )

    def test_empty_unit_becomes_none(self):
        self.assertIsNone(normalize_unit(None))
        self.assertIsNone(normalize_unit("   "))

    def test_rejects_unknown_unit(self):
        with self.assertRaises(ValueError):
            normalize_unit("bananas")


class ParseMeasurementTests(unittest.TestCase):
    def test_parses_value_and_unit_without_space(self):
        measurement = parse_measurement("12,476.5ng/ml")

        self.assertEqual(measurement.value, Decimal("12476.5"))
        self.assertEqual(measurement.unit, "ng/mL")
        self.assertEqual(measurement.raw_text, "12,476.5ng/ml")

    def test_parses_unit_written_in_words(self):
        measurement = parse_measurement("6100 per microliter")

        self.assertEqual(measurement.value, Decimal("6100"))
        self.assertEqual(measurement.unit, "/µL")

    def test_accepts_measurement_without_unit(self):
        measurement = parse_measurement("42")

        self.assertEqual(measurement.value, Decimal("42"))
        self.assertIsNone(measurement.unit)

class ParseReferenceRangeTests(unittest.TestCase):
    def test_parses_closed_range(self):
        reference = parse_reference_range("0-0.04 ng/mL")

        self.assertEqual(reference.low, Decimal("0"))
        self.assertEqual(reference.high, Decimal("0.04"))
        self.assertEqual(reference.unit, "ng/mL")
        self.assertEqual(reference.raw_text, "0-0.04 ng/mL")

    def test_parses_percentage_on_both_limits(self):
        reference = parse_reference_range("55%-75%")

        self.assertEqual(reference.low, Decimal("55"))
        self.assertEqual(reference.high, Decimal("75"))
        self.assertEqual(reference.unit, "%")

    def test_accepts_normal_range_prefix(self):
        reference = parse_reference_range(
            "normal range, 10-140 U/L"
        )

        self.assertEqual(reference.low, Decimal("10"))
        self.assertEqual(reference.high, Decimal("140"))
        self.assertEqual(reference.unit, "U/L")

    def test_parses_open_upper_limit(self):
        reference = parse_reference_range("<20")

        self.assertIsNone(reference.low)
        self.assertEqual(reference.high, Decimal("20"))
        self.assertIsNone(reference.unit)

    def test_parses_inclusive_open_upper_limit(self):
        reference = parse_reference_range("<=10 AU/mL")

        self.assertIsNone(reference.low)
        self.assertEqual(reference.high, Decimal("10"))
        self.assertEqual(reference.unit, "AU/mL")

    def test_parses_open_lower_limit(self):
        reference = parse_reference_range(">5 mg/dL")

        self.assertEqual(reference.low, Decimal("5"))
        self.assertIsNone(reference.high)
        self.assertEqual(reference.unit, "mg/dL")

    def test_rejects_incompatible_units(self):
        with self.assertRaises(ValueError):
            parse_reference_range("55%-75 mg/dL")

    def test_rejects_invalid_range(self):
        with self.assertRaises(ValueError):
            parse_reference_range("between ten and twenty")

if __name__ == "__main__":
    unittest.main()