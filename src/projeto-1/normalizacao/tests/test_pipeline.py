"""Testes de ponta a ponta do pipeline e da exportação."""

import csv
import io
import json

import tempfile
import unittest
from contextlib import redirect_stdout
from decimal import Decimal
from pathlib import Path


from normalizacao.case_reader import ClinicalCase
from normalizacao.main import main
from normalizacao.pipeline import process_case, process_case_from_csv
from normalizacao.exporters.csv_exporter import EDGE_COLUMNS, NODE_COLUMNS, export_pipeline_result


CASE_TEXT = (
    "A 44-year-old woman with a past medical history of hypertension "
    "presented with nausea. Computed tomography (CT) demonstrated a "
    "6 cm cystic lesion near the pancreas. Laboratory tests showed elevated "
    "serum lipase at 850 U/L (reference range 10-140 U/L). The patient "
    "was diagnosed with pancreatitis based on imaging. The patient received "
    "oral prednisone 25 mg once daily and was treated with intravenous fluids. "
    "The patient was discharged home on day 4."
)


def _case() -> ClinicalCase:
    return ClinicalCase(
        article_id="PMC5137649",
        age=Decimal("44"),
        case_id="PMC5137649_01",
        case_text=CASE_TEXT,
        gender="Female",
    )


def _write_cases_csv(directory: str) -> Path:
    path = Path(directory) / "cases.csv"
    with path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=("article_id", "age", "case_id", "case_text", "gender"),
        )
        writer.writeheader()
        writer.writerow(
            {
                "article_id": "PMC5137649",
                "age": "44",
                "case_id": "PMC5137649_01",
                "case_text": CASE_TEXT,
                "gender": "Female",
            }
        )
    return path


class PipelineTests(unittest.TestCase):
    def test_processes_all_supported_entity_groups(self):
        result = process_case(_case())
        node_types = {node.type for node in result.graph.nodes}

        self.assertTrue(
            {
                "Patient",
                "History",
                "Symptom",
                "Exam",
                "ExamResult",
                "Finding",
                "AnatomicalSite",
                "Diagnosis",
                "Medication",
                "Treatment",
                "Outcome",
            }.issubset(node_types)
        )

    def test_builds_graph_relations(self):
        result = process_case(_case())
        relations = {edge.relation for edge in result.graph.edges}

        self.assertTrue(
            {
                "HAS_HISTORY",
                "HAS_SYMPTOM",
                "UNDERWENT_EXAM",
                "HAS_RESULT",
                "REVEALS",
                "LOCATED_IN",
                "DIAGNOSED_WITH",
                "TREATED_WITH",
                "HAS_OUTCOME",
            }.issubset(relations)
        )

    def test_processes_case_selected_from_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            csv_path = _write_cases_csv(directory)
            result = process_case_from_csv(csv_path, "PMC5137649_01")

        self.assertEqual(result.case.case_id, "PMC5137649_01")
        self.assertGreater(len(result.graph.nodes), 1)
        self.assertGreater(len(result.graph.edges), 1)


class SerializationTests(unittest.TestCase):
    def test_exports_contract_tables_and_impact(self):
        result = process_case(_case())

        with tempfile.TemporaryDirectory() as directory:
            paths = export_pipeline_result(result, directory)

            with paths.nodes.open(encoding="utf-8", newline="") as csv_file:
                node_reader = csv.DictReader(csv_file)
                node_rows = list(node_reader)
                self.assertEqual(tuple(node_reader.fieldnames or ()), NODE_COLUMNS)

            with paths.edges.open(encoding="utf-8", newline="") as csv_file:
                edge_reader = csv.DictReader(csv_file)
                edge_rows = list(edge_reader)
                self.assertEqual(tuple(edge_reader.fieldnames or ()), EDGE_COLUMNS)

            impact = json.loads(paths.impact.read_text(encoding="utf-8"))
            graph_markdown = paths.graph.read_text(encoding="utf-8")

        self.assertGreater(len(node_rows), 0)
        self.assertGreater(len(edge_rows), 0)
        self.assertEqual(impact["case_id"], "PMC5137649_01")
        self.assertIn("nodes_merged", impact)
        self.assertEqual(
            impact["acronyms"]["CT"].casefold(),
            "computed tomography",
        )
        self.assertIn("```mermaid", graph_markdown)
        self.assertIn('"nodeSpacing": 35, "rankSpacing": 140', graph_markdown)
        self.assertIn("flowchart LR", graph_markdown)
        self.assertIn("P1 -->|HAS_SYMPTOM|", graph_markdown)
        self.assertIn('<b>Patient</b><br/>44yo Female', graph_markdown)
        self.assertNotIn("modality=imaging", graph_markdown)


class CommandLineTests(unittest.TestCase):
    def test_main_generates_three_files(self):
        with tempfile.TemporaryDirectory() as directory:
            csv_path = _write_cases_csv(directory)
            output = Path(directory) / "output"
            printed = io.StringIO()

            with redirect_stdout(printed):
                exit_code = main(
                    [
                        "--cases",
                        str(csv_path),
                        "--case-id",
                        "PMC5137649_01",
                        "--output",
                        str(output),
                    ]
                )

            generated = sorted(path.name for path in output.iterdir())

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            generated,
            [
                "PMC5137649_01-edges.csv",
                "PMC5137649_01-graph.md",
                "PMC5137649_01-impact.json",
                "PMC5137649_01-nodes.csv",
            ],
        )
        self.assertIn("nodes:", printed.getvalue())
        self.assertIn("edges:", printed.getvalue())
        self.assertIn("impact:", printed.getvalue())
        self.assertIn("graph:", printed.getvalue())


if __name__ == "__main__":
    unittest.main()
