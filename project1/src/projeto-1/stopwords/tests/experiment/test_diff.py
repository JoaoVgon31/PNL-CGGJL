import unittest

from stopwords.core.graph import GraphBuilder
from stopwords.experiment.diff import diff_graphs
from stopwords.experiment.conditions import Condition
from stopwords.case_reader import ClinicalCase
from stopwords.pipeline import process_case


class DiffGraphsSyntheticTests(unittest.TestCase):
    def test_detects_lost_node(self):
        baseline = GraphBuilder("PMC1234567_01")
        baseline.add_node("Symptom", "nausea")
        variant = GraphBuilder("PMC1234567_01")

        result = diff_graphs(baseline, variant)
        self.assertEqual(result.nodes_lost, 1)
        self.assertEqual(result.nodes_gained, 0)

    def test_detects_gained_node(self):
        baseline = GraphBuilder("PMC1234567_01")
        variant = GraphBuilder("PMC1234567_01")
        variant.add_node("Symptom", "nausea")

        result = diff_graphs(baseline, variant)
        self.assertEqual(result.nodes_gained, 1)

    def test_detects_polarity_change(self):
        baseline = GraphBuilder("PMC1234567_01")
        baseline.add_node("Finding", "malignancy", {"polarity": "absent"})
        variant = GraphBuilder("PMC1234567_01")
        variant.add_node("Finding", "malignancy", {"polarity": "present"})

        result = diff_graphs(baseline, variant)
        self.assertEqual(result.polarity_changed, 1)
        self.assertIn("Finding:malignancy absent->present", result.polarity_changed_examples)

    def test_ignores_polarity_on_types_without_it(self):
        baseline = GraphBuilder("PMC1234567_01")
        baseline.add_node("Exam", "CT scan", {"modality": "imaging"})
        variant = GraphBuilder("PMC1234567_01")
        variant.add_node("Exam", "CT scan", {"modality": "laboratory"})

        result = diff_graphs(baseline, variant)
        self.assertEqual(result.polarity_changed, 0)

    def test_detects_lost_edge(self):
        baseline = GraphBuilder("PMC1234567_01")
        patient = baseline.add_node("Patient", "patient")
        symptom = baseline.add_node("Symptom", "nausea")
        baseline.add_edge(patient.node_id, symptom.node_id, "HAS_SYMPTOM")

        variant = GraphBuilder("PMC1234567_01")
        variant.add_node("Patient", "patient")
        variant.add_node("Symptom", "nausea")  # node exists but edge doesn't

        result = diff_graphs(baseline, variant)
        self.assertEqual(result.edges_lost, 1)


class DiffGraphsRealPipelineTests(unittest.TestCase):
    """Regression guard: GUARDED_LABEL must never flip polarity, no matter the list."""

    def test_guarded_label_never_flips_polarity_in_diff(self):
        case = ClinicalCase(
            article_id="PMC1", age=None, case_id="PMC1234567_01",
            case_text="FNA of the cyst demonstrated no evidence of malignancy.",
            gender="Female",
        )
        baseline = process_case(case, Condition.BASELINE)
        for wordlist in ("nltk_stopwords", "spacy_stopwords", "custom_clinical"):
            guarded = process_case(case, Condition.GUARDED_LABEL, wordlist)

            # Existing check: diff_graphs still reports no polarity_changed among matched nodes.
            result = diff_graphs(baseline.graph, guarded.graph)
            self.assertEqual(result.polarity_changed, 0, f"GUARDED_LABEL flipped polarity with {wordlist}")

            # Stronger, direct check: confirm the negation actually survived in the guarded
            # run's own graph, independent of whether the label matched baseline's (which
            # diff_graphs' (type,label) matching can miss when label-cleaning changes the
            # label text itself).
            guarded_findings = [n for n in guarded.graph.nodes if n.type == "Finding"]
            self.assertTrue(
                any(n.attributes.get("polarity") == "absent" for n in guarded_findings),
                f"GUARDED_LABEL with {wordlist} lost the negated Finding entirely: {guarded_findings}",
            )

    def test_naive_unprotected_flips_polarity_with_a_list_lacking_the_cue(self):
        case = ClinicalCase(
            article_id="PMC1", age=None, case_id="PMC1234567_01",
            case_text="No recurrence of the parastomal hernia was identified.",
            gender="Female",
        )
        baseline = process_case(case, Condition.BASELINE)
        naive = process_case(case, Condition.NAIVE_UNPROTECTED, "spacy_stopwords")
        result = diff_graphs(baseline.graph, naive.graph)
        # single-token label ("recurrence") survives masking intact, so diff_graphs'
        # (type, label) matcher keeps the node paired across baseline/variant and the
        # polarity flip is directly visible instead of manifesting as nodes_lost/gained.
        self.assertEqual(result.polarity_changed, 1)


if __name__ == "__main__":
    unittest.main()
