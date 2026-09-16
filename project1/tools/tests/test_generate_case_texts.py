import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generate_case_texts import generate


class GenerateTests(unittest.TestCase):
    def test_copies_case_id_and_case_text_columns_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            cases_csv = Path(tmp) / "cases.csv"
            with cases_csv.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=("article_id", "age", "case_id", "case_text", "gender")
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "article_id": "PMC1",
                        "age": "44.0",
                        "case_id": "PMC1_01",
                        "case_text": "A patient, with a comma, presented.",
                        "gender": "Female",
                    }
                )
            output_csv = Path(tmp) / "case_texts.csv"

            count = generate(cases_csv, output_csv)

            self.assertEqual(count, 1)
            with output_csv.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(
                rows, [{"case_id": "PMC1_01", "case_text": "A patient, with a comma, presented."}]
            )
            self.assertEqual(list(rows[0].keys()), ["case_id", "case_text"])


if __name__ == "__main__":
    unittest.main()
