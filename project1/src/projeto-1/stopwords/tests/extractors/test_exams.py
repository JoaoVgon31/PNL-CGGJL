import unittest

from stopwords.extractors.exams import extract_exam_results, extract_exams


class ExtractExamsTests(unittest.TestCase):
    def test_extracts_exam_after_underwent(self):
        text = "She underwent contrast enhanced computed tomography."
        mentions = extract_exams(text)
        self.assertTrue(mentions)
        self.assertEqual(mentions[0].attributes["modality"], "imaging")
        self.assertTrue(mentions[0].attributes["contrast"])

    def test_extracts_abbreviation(self):
        text = "She underwent carcinoembryonic antigen (CEA) testing."
        mentions = extract_exams(text)
        self.assertEqual(mentions[0].attributes["abbreviation"], "CEA")

    def test_no_trigger_no_mentions(self):
        self.assertEqual(extract_exams("The patient rested."), [])

    def test_offset_bug_regression_repeated_label_without_sentence_split(self):
        # Regression test for offset bug when label appears multiple times
        # in same sentence (no period/semicolon to split on).
        # Before fix: would capture first "imaging" at position 6 (wrong)
        # After fix: should capture second "imaging" at position 46 (correct)
        text = "Prior imaging suggested a mass; she underwent imaging and blood tests."
        mentions = extract_exams(text)
        self.assertTrue(mentions)
        self.assertEqual(mentions[0].label, "imaging")
        # Verify we captured the correct text
        self.assertEqual(text[mentions[0].char_start:mentions[0].char_end], "imaging")
        # Verify we captured the SECOND occurrence (position 46), not the first (position 6)
        first_imaging_pos = text.find("imaging")
        second_imaging_pos = text.find("imaging", first_imaging_pos + 1)
        self.assertEqual(mentions[0].char_start, second_imaging_pos,
                         f"Should capture at position {second_imaging_pos} (second occurrence), not {first_imaging_pos} (first occurrence)")


class ExtractExamResultsTests(unittest.TestCase):
    def test_extracts_value_and_unit(self):
        text = "a carcinoembryonic antigen level of 12476.5ng/ml"
        mentions = extract_exam_results(text)
        self.assertTrue(mentions)
        self.assertEqual(mentions[0].attributes["value"], "12476.5")
        self.assertEqual(mentions[0].attributes["unit"], "ng/ml")

    def test_extracts_qualitative_result(self):
        text = "Donath-Landsteiner test of positive"
        mentions = extract_exam_results(text)
        self.assertTrue(any(m.attributes["value"] == "positive" for m in mentions))

    def test_extracts_reference_range(self):
        text = "normal troponin I of 0.016 ng/mL (normal range, 0-0.04 ng/mL)"
        mentions = extract_exam_results(text)
        self.assertTrue(mentions)
        self.assertIsNotNone(mentions[0].attributes["reference_range_raw"])


if __name__ == "__main__":
    unittest.main()
