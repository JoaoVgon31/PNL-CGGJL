import unittest
from pathlib import Path

from stopwords.experiment.conditions import Condition
from stopwords.experiment.runner import run_case, run_experiment

_FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "cases.csv"


class RunCaseTests(unittest.TestCase):
    def test_returns_nine_variants(self):
        results = run_case(str(_FIXTURE), "PMC0000001_01")
        self.assertEqual(len(results), 9)

        combos = {(r.condition, r.wordlist) for r in results}
        self.assertEqual(len(combos), 9)
        for condition in (Condition.NAIVE_UNPROTECTED, Condition.GUARDED_GLOBAL, Condition.GUARDED_LABEL):
            self.assertTrue(any(r.condition is condition for r in results))

    def test_all_diffs_reference_the_case_id(self):
        results = run_case(str(_FIXTURE), "PMC0000001_01")
        for result in results:
            self.assertEqual(result.diff.case_id, "PMC0000001_01")


class RunExperimentTests(unittest.TestCase):
    def test_runs_over_multiple_cases(self):
        results = run_experiment(str(_FIXTURE), ["PMC0000001_01", "PMC0000002_01"])
        self.assertEqual(len(results), 18)  # 9 variants x 2 cases


if __name__ == "__main__":
    unittest.main()
