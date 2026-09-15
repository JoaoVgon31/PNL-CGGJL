"""Testes da construção de resultados laboratoriais."""


import unittest
from decimal import Decimal



from normalizacao.extractors.results import find_lab_result_candidates


class FindLabResultCandidatesTests(unittest.TestCase):
    def test_associates_range_in_same_sentence(self):
        text = (
            "Lipase was 850 U/L "
            "(reference range 10-140 U/L)."
        )

        results = find_lab_result_candidates(text)

        self.assertEqual(len(results), 1)

        result = results[0]
        self.assertEqual(
            result.measurement.measurement.value,
            Decimal("850"),
        )
        self.assertIsNotNone(result.reference_range)
        self.assertEqual(
            result.reference_range.reference_range.low,
            Decimal("10"),
        )
        self.assertEqual(
            result.reference_range.reference_range.high,
            Decimal("140"),
        )

    def test_does_not_use_range_from_another_sentence(self):
        text = (
            "Lipase was 850 U/L. "
            "The reference range was 10-140 U/L."
        )

        result = find_lab_result_candidates(text)[0]

        self.assertIsNone(result.reference_range)

    def test_does_not_associate_incompatible_unit(self):
        text = (
            "The result was 5 mg/dL "
            "(reference range 10-140 U/L)."
        )

        result = find_lab_result_candidates(text)[0]

        self.assertIsNone(result.reference_range)

    def test_uses_nearest_compatible_range(self):
        text = (
            "Marker A was 5 mg/dL, reference range 1-8 mg/dL, "
            "and marker B was 90 mg/dL, "
            "reference range 70-100 mg/dL."
        )

        results = find_lab_result_candidates(text)

        self.assertEqual(len(results), 2)
        self.assertEqual(
            results[0].reference_range.reference_range.low,
            Decimal("1"),
        )
        self.assertEqual(
            results[1].reference_range.reference_range.low,
            Decimal("70"),
        )

    def test_preserves_sentence_and_offsets(self):
        text = (
            "An earlier sentence. "
            "Troponin was 0.016 ng/mL on admission. "
            "A later sentence."
        )

        result = find_lab_result_candidates(text)[0]

        self.assertEqual(
            result.evidence_text,
            "Troponin was 0.016 ng/mL on admission.",
        )
        self.assertEqual(
            text[result.char_start:result.char_end],
            result.evidence_text,
        )

    def test_keeps_result_without_reference_range(self):
        text = "C-reactive protein was 96 mg/L."

        result = find_lab_result_candidates(text)[0]

        self.assertEqual(
            result.measurement.measurement.value,
            Decimal("96"),
        )
        self.assertIsNone(result.reference_range)

    def test_rejects_non_string_input(self):
        with self.assertRaises(TypeError):
            find_lab_result_candidates(None)

class ResultInterpretationTests(unittest.TestCase):
    def test_uses_stated_interpretation(self):
        text = "C-reactive protein was elevated at 96 mg/L."

        result = find_lab_result_candidates(text)[0]

        self.assertEqual(result.interpretation, "elevated")
        self.assertEqual(
            result.interpretation_source,
            "stated",
        )

    def test_stated_interpretation_has_priority(self):
        text = (
            "The stated normal result was 200 U/L "
            "(reference range 10-140 U/L)."
        )

        result = find_lab_result_candidates(text)[0]

        self.assertEqual(result.interpretation, "normal")
        self.assertEqual(
            result.interpretation_source,
            "stated",
        )

    def test_normal_range_is_not_stated_interpretation(self):
        text = (
            "Lipase was 850 U/L "
            "(normal range 10-140 U/L)."
        )

        result = find_lab_result_candidates(text)[0]

        self.assertEqual(result.interpretation, "elevated")
        self.assertEqual(
            result.interpretation_source,
            "derived",
        )

    def test_derives_normal_result(self):
        text = (
            "Troponin was 0.016 ng/mL "
            "(reference range 0-0.04 ng/mL)."
        )

        result = find_lab_result_candidates(text)[0]

        self.assertEqual(result.interpretation, "normal")
        self.assertEqual(
            result.interpretation_source,
            "derived",
        )

    def test_derives_decreased_result(self):
        text = (
            "The result was 5 U/L "
            "(reference range 10-140 U/L)."
        )

        result = find_lab_result_candidates(text)[0]

        self.assertEqual(result.interpretation, "decreased")
        self.assertEqual(
            result.interpretation_source,
            "derived",
        )

    def test_keeps_interpretation_empty_without_evidence(self):
        text = "C-reactive protein was 96 mg/L."

        result = find_lab_result_candidates(text)[0]

        self.assertIsNone(result.interpretation)
        self.assertIsNone(result.interpretation_source)

    def test_uses_closest_interpretation(self):
        text = (
            "Marker A was normal at 5 mg/dL, while marker B "
            "was elevated at 90 mg/dL."
        )

        results = find_lab_result_candidates(text)

        self.assertEqual(results[0].interpretation, "normal")
        self.assertEqual(results[1].interpretation, "elevated")


if __name__ == "__main__":
    unittest.main()