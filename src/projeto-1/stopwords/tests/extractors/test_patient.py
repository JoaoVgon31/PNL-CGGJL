import unittest

from stopwords.case_reader import ClinicalCase
from stopwords.extractors.patient import extract_patient_attributes


class ExtractPatientAttributesTests(unittest.TestCase):
    def test_prefers_age_from_text_over_csv(self):
        case = ClinicalCase(
            article_id="PMC1", age="7", case_id="PMC1_01",
            case_text="A 44-year-old woman presented with pain.", gender="Female",
        )
        attrs = extract_patient_attributes(case, case.case_text)
        self.assertEqual(attrs["age"], "44")
        self.assertEqual(attrs["age_unit"], "years")

    def test_falls_back_to_csv_age_when_text_has_none(self):
        case = ClinicalCase(
            article_id="PMC1", age="7", case_id="PMC1_01",
            case_text="A patient presented with pain.", gender="Male",
        )
        attrs = extract_patient_attributes(case, case.case_text)
        self.assertEqual(attrs["age"], "7")
        self.assertEqual(attrs["age_unit"], "years")

    def test_detects_gestational_age(self):
        case = ClinicalCase(
            article_id="PMC1", age=None, case_id="PMC1_01",
            case_text="born at 33 weeks gestational age to a 36-year-old mother",
            gender="Male",
        )
        attrs = extract_patient_attributes(case, case.case_text)
        self.assertEqual(attrs["age"], "33")
        self.assertEqual(attrs["age_unit"], "weeks_gestational")

    def test_always_includes_case_and_article_id(self):
        case = ClinicalCase(article_id="PMC1", age=None, case_id="PMC1_01", case_text="No age here.", gender="Unknown")
        attrs = extract_patient_attributes(case, case.case_text)
        self.assertEqual(attrs["case_id"], "PMC1_01")
        self.assertEqual(attrs["article_id"], "PMC1")
        self.assertEqual(attrs["gender"], "Unknown")


if __name__ == "__main__":
    unittest.main()
