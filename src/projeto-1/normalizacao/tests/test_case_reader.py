"""Testes da leitura de casos clínicos."""

import csv

import tempfile
import unittest
from decimal import Decimal
from pathlib import Path



from normalizacao.case_reader import read_case


class ReadCaseTests(unittest.TestCase):
    def _write_csv(
        self,
        directory: str,
        rows: list[dict[str, str]],
        fieldnames: list[str] | None = None,
    ) -> Path:
        path = Path(directory) / "cases.csv"
        columns = fieldnames or [
            "article_id",
            "age",
            "case_id",
            "case_text",
            "gender",
        ]

        with path.open(
            mode="w",
            encoding="utf-8",
            newline="",
        ) as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=columns,
            )
            writer.writeheader()
            writer.writerows(rows)

        return path

    def test_reads_requested_case(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._write_csv(
                directory,
                [
                    {
                        "article_id": "PMC5137649",
                        "age": "44.0",
                        "case_id": "PMC5137649_01",
                        "case_text": (
                            "A patient underwent CT.\n"
                            "The examination revealed a lesion."
                        ),
                        "gender": "Female",
                    }
                ],
            )

            case = read_case(path, "PMC5137649_01")

            self.assertEqual(case.article_id, "PMC5137649")
            self.assertEqual(case.age, Decimal("44.0"))
            self.assertEqual(case.gender, "Female")
            self.assertIn("\n", case.case_text)

    def test_accepts_missing_age(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._write_csv(
                directory,
                [
                    {
                        "article_id": "PMC123",
                        "age": "",
                        "case_id": "PMC123_01",
                        "case_text": "Clinical text.",
                        "gender": "Unknown",
                    }
                ],
            )

            case = read_case(path, "PMC123_01")

            self.assertIsNone(case.age)

    def test_rejects_missing_case(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._write_csv(directory, [])

            with self.assertRaises(LookupError):
                read_case(path, "PMC999_01")

    def test_rejects_duplicate_case_id(self):
        with tempfile.TemporaryDirectory() as directory:
            row = {
                "article_id": "PMC123",
                "age": "44",
                "case_id": "PMC123_01",
                "case_text": "Clinical text.",
                "gender": "Female",
            }
            path = self._write_csv(directory, [row, row])

            with self.assertRaises(ValueError):
                read_case(path, "PMC123_01")

    def test_rejects_missing_columns(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._write_csv(
                directory,
                [],
                fieldnames=["case_id", "case_text"],
            )

            with self.assertRaises(ValueError):
                read_case(path, "PMC123_01")

    def test_rejects_invalid_age(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self._write_csv(
                directory,
                [
                    {
                        "article_id": "PMC123",
                        "age": "unknown age",
                        "case_id": "PMC123_01",
                        "case_text": "Clinical text.",
                        "gender": "Unknown",
                    }
                ],
            )

            with self.assertRaises(ValueError):
                read_case(path, "PMC123_01")


if __name__ == "__main__":
    unittest.main()