"""Testes do contrato caso → tokens → nós/arestas."""

import csv
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path


SOURCE = Path(__file__).parents[1]
sys.path.insert(0, str(SOURCE))

from case_reader import read_case  # noqa: E402
from models import ClinicalCase  # noqa: E402
from pipeline import process_case  # noqa: E402
from serialization import export_pipeline_result  # noqa: E402
from tokenizers import ClinicalRegexTokenizer, WhitespaceTokenizer  # noqa: E402


CASE_TEXT = (
    "A 44-year-old woman presented with a 3-day history of abdominal pain "
    "associated with nausea. Computed tomography demonstrated a 6cm cystic "
    "lesion between the stomach and body/tail of the pancreas (Fig 1). "
    "A carcinoembryonic antigen (CEA) level of 12,476.5ng/ml suggested a "
    "mucinous pancreatic cystic neoplasm. Final pathology was consistent with "
    "a gastric duplication cyst. The patient was discharged home."
)


def make_case():
    return ClinicalCase(
        article_id="PMC5137649",
        age=Decimal("44"),
        case_id="PMC5137649_01",
        case_text=CASE_TEXT,
        gender="Female",
    )


class PipelineTests(unittest.TestCase):
    def test_generates_contract_nodes_and_edges(self):
        result = process_case(make_case(), ClinicalRegexTokenizer())
        node_types = {node.type for node in result.graph.nodes}
        self.assertTrue({"Patient", "Symptom", "Exam", "ExamResult", "Finding", "Diagnosis"} <= node_types)
        relations = {edge.relation for edge in result.graph.edges}
        self.assertTrue({"HAS_SYMPTOM", "UNDERWENT_EXAM", "HAS_RESULT", "DIAGNOSED_WITH"} <= relations)

    def test_extracts_glued_value_and_unit(self):
        result = process_case(make_case(), ClinicalRegexTokenizer())
        lab_results = [node for node in result.graph.nodes if node.type == "ExamResult"]
        self.assertTrue(
            any(
                node.attributes.get("value") == Decimal("12476.5")
                and node.attributes.get("unit") == "ng/mL"
                and node.attributes.get("raw_text") == "12,476.5ng/ml"
                for node in lab_results
            )
        )

    def test_tokenizer_changes_graph_yield(self):
        clinical = process_case(make_case(), ClinicalRegexTokenizer())
        whitespace = process_case(make_case(), WhitespaceTokenizer())
        clinical_results = sum(node.type == "ExamResult" for node in clinical.graph.nodes)
        whitespace_results = sum(node.type == "ExamResult" for node in whitespace.graph.nodes)
        self.assertGreater(clinical_results, whitespace_results)

    def test_all_edge_offsets_recover_evidence(self):
        result = process_case(make_case(), ClinicalRegexTokenizer())
        for edge in result.graph.edges:
            start = edge.attributes["char_start"]
            end = edge.attributes["char_end"]
            self.assertEqual(CASE_TEXT[start:end], edge.attributes["evidence_text"])

    def test_figure_reference_does_not_enter_diagnosis_label(self):
        result = process_case(make_case(), ClinicalRegexTokenizer())
        diagnoses = [node.label for node in result.graph.nodes if node.type == "Diagnosis"]
        self.assertTrue(all("fig" not in label.casefold() for label in diagnoses))


class InputOutputTests(unittest.TestCase):
    def test_reads_case_and_exports_three_csv_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "cases.csv"
            with source.open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=("article_id", "age", "case_id", "case_text", "gender"),
                )
                writer.writeheader()
                writer.writerow({
                    "article_id": "PMC5137649",
                    "age": "44.0",
                    "case_id": "PMC5137649_01",
                    "case_text": CASE_TEXT,
                    "gender": "Female",
                })
            case = read_case(source, "PMC5137649_01")
            result = process_case(case, ClinicalRegexTokenizer())
            paths = export_pipeline_result(result, root / "output")
            self.assertTrue(paths.nodes.exists())
            self.assertTrue(paths.edges.exists())
            self.assertTrue(paths.tokens.exists())
            self.assertTrue(paths.graph.exists())
            self.assertTrue(paths.slide_graph.exists())
            self.assertIn("HAS_RESULT", paths.slide_graph.read_text(encoding="utf-8"))
            with paths.nodes.open(encoding="utf-8", newline="") as stream:
                self.assertEqual(
                    tuple(csv.DictReader(stream).fieldnames),
                    ("case_id", "node_id", "type", "label", "attributes"),
                )


if __name__ == "__main__":
    unittest.main()
