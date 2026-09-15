import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from stopwords.main import main

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "cases.csv"


class MainTests(unittest.TestCase):
    def test_processes_single_case(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code = main(["--cases", str(_FIXTURE), "--case-id", "PMC0000001_01", "--output", tmp_dir])
            self.assertEqual(exit_code, 0)
            self.assertTrue((Path(tmp_dir) / "PMC0000001_01-nodes.csv").exists())

    def test_processes_all_cases(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            exit_code = main(["--cases", str(_FIXTURE), "--all-cases", "--output", tmp_dir])
            self.assertEqual(exit_code, 0)
            self.assertTrue((Path(tmp_dir) / "PMC0000001_01-nodes.csv").exists())
            self.assertTrue((Path(tmp_dir) / "PMC0000002_01-nodes.csv").exists())

    def test_requires_case_id_or_all_cases(self):
        with self.assertRaises(SystemExit):
            main(["--cases", str(_FIXTURE)])

    def test_missing_wordlist_with_non_baseline_condition(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                exit_code = main([
                    "--cases", str(_FIXTURE),
                    "--case-id", "PMC0000001_01",
                    "--condition", "NAIVE_UNPROTECTED",
                    "--output", tmp_dir
                ])
            self.assertEqual(exit_code, 1)
            self.assertIn("erro ao processar", stderr.getvalue())

    def test_unknown_case_id(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                exit_code = main([
                    "--cases", str(_FIXTURE),
                    "--case-id", "NOPE_99",
                    "--output", tmp_dir
                ])
            self.assertEqual(exit_code, 1)
            self.assertIn("erro ao processar", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
