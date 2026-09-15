import unittest
from pathlib import Path

from stopwords.case_reader import read_all_case_ids, read_case

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "cases.csv"


class ReadCaseTests(unittest.TestCase):
    def test_reads_matching_case(self):
        case = read_case(_FIXTURE, "PMC0000001_01")
        self.assertEqual(case.case_id, "PMC0000001_01")
        self.assertEqual(case.article_id, "PMC0000001")
        self.assertEqual(case.gender, "Female")
        self.assertIn("presented with", case.case_text)

    def test_missing_case_id_raises_lookup_error(self):
        with self.assertRaises(LookupError):
            read_case(_FIXTURE, "PMC9999999_99")

    def test_read_all_case_ids(self):
        self.assertEqual(
            read_all_case_ids(_FIXTURE),
            ["PMC0000001_01", "PMC0000002_01"],
        )


if __name__ == "__main__":
    unittest.main()
