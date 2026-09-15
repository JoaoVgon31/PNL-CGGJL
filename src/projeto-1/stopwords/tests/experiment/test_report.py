import json
import tempfile
import unittest
from pathlib import Path

from stopwords.experiment.conditions import Condition
from stopwords.experiment.diff import CaseDiff
from stopwords.experiment.report import summarize, write_summary
from stopwords.experiment.runner import VariantResult


def _variant(condition, wordlist, case_id, polarity_changed=0, nodes_lost=0, edges_lost=0):
    return VariantResult(
        condition=condition,
        wordlist=wordlist,
        diff=CaseDiff(
            case_id=case_id, nodes_lost=nodes_lost, nodes_gained=0,
            polarity_changed=polarity_changed, edges_lost=edges_lost, edges_gained=0,
            polarity_changed_examples=(),
        ),
    )


class SummarizeTests(unittest.TestCase):
    def test_aggregates_totals_per_condition_and_wordlist(self):
        results = [
            _variant(Condition.NAIVE_UNPROTECTED, "spacy_stopwords", "CASE_A", polarity_changed=2),
            _variant(Condition.NAIVE_UNPROTECTED, "spacy_stopwords", "CASE_B", polarity_changed=1),
            _variant(Condition.GUARDED_LABEL, "spacy_stopwords", "CASE_A", polarity_changed=0),
        ]
        rows = summarize(results)
        naive_row = next(r for r in rows if r["condition"] == "NAIVE_UNPROTECTED" and r["wordlist"] == "spacy_stopwords")
        self.assertEqual(naive_row["polarity_changed"], 3)
        self.assertEqual(naive_row["worst_case_id"], "CASE_A")

    def test_write_summary_produces_csv_and_json(self):
        rows = summarize([_variant(Condition.GUARDED_GLOBAL, "nltk_stopwords", "CASE_A", edges_lost=4)])
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path, json_path = write_summary(rows, tmp_dir)
            self.assertTrue(csv_path.exists())
            self.assertTrue(json_path.exists())
            with json_path.open() as handle:
                loaded = json.load(handle)
            self.assertEqual(loaded[0]["edges_lost"], 4)


if __name__ == "__main__":
    unittest.main()
