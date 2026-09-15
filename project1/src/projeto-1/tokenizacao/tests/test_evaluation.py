import sys
import unittest
from decimal import Decimal
from pathlib import Path


SOURCE = Path(__file__).parents[1]
sys.path.insert(0, str(SOURCE))

from evaluation import evaluate_challenges  # noqa: E402
from models import ClinicalCase  # noqa: E402
from evaluation import compare_case  # noqa: E402
from tokenizers import ClinicalRegexTokenizer  # noqa: E402


class EvaluationTests(unittest.TestCase):
    def test_clinical_tokenizer_passes_all_challenges(self):
        result = evaluate_challenges(ClinicalRegexTokenizer())
        self.assertEqual(result["passed"], result["total"])

    def test_compare_case_reports_graph_metrics(self):
        case = ClinicalCase(
            "PMC1",
            Decimal("52"),
            "PMC1_01",
            "A 52-year-old man had lipase of 850 U/L.",
            "Male",
        )
        report = compare_case(case)
        self.assertIn("clinical_regex", report["tokenizers"])
        self.assertIn("graph", report["tokenizers"]["clinical_regex"])


if __name__ == "__main__":
    unittest.main()
