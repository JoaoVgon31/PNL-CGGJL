import unittest
from pathlib import Path

from stopwords.case_reader import read_case
from stopwords.experiment.conditions import Condition
from stopwords.pipeline import process_case, process_case_from_csv

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "cases.csv"


class ProcessCaseTests(unittest.TestCase):
    def test_baseline_produces_patient_node(self):
        case = read_case(_FIXTURE, "PMC0000001_01")
        result = process_case(case)
        types = {node.type for node in result.graph.nodes}
        self.assertIn("Patient", types)

    def test_baseline_extracts_multiple_entity_types(self):
        case = read_case(_FIXTURE, "PMC0000001_01")
        result = process_case(case)
        types = {node.type for node in result.graph.nodes}
        self.assertTrue({"Symptom", "Finding", "Exam", "Diagnosis", "Treatment", "Medication", "Outcome"} <= types)

    def test_naive_unprotected_can_flip_finding_polarity(self):
        case = read_case(_FIXTURE, "PMC0000001_01")
        baseline = process_case(case, Condition.BASELINE)
        naive = process_case(case, Condition.NAIVE_UNPROTECTED, "spacy_stopwords")

        baseline_finding = next(
            n for n in baseline.graph.nodes
            if n.type == "Finding" and n.attributes.get("polarity") == "absent"
        )
        self.assertEqual(baseline_finding.attributes["polarity"], "absent")

        naive_findings = [n for n in naive.graph.nodes if n.type == "Finding"]
        # under NAIVE_UNPROTECTED with spacy (which contains "no"), the negation cue is
        # masked before extraction runs — no Finding node in the naive run should still
        # report polarity=absent for this case.
        self.assertFalse(
            any(n.attributes.get("polarity") == "absent" for n in naive_findings),
            f"expected the negation cue to be lost under NAIVE_UNPROTECTED, but found: {naive_findings}",
        )

    def test_process_case_from_csv(self):
        result = process_case_from_csv(_FIXTURE, "PMC0000001_01")
        self.assertEqual(result.case.case_id, "PMC0000001_01")

    def test_non_baseline_requires_wordlist(self):
        case = read_case(_FIXTURE, "PMC0000001_01")
        with self.assertRaises(ValueError):
            process_case(case, Condition.GUARDED_LABEL)


if __name__ == "__main__":
    unittest.main()
