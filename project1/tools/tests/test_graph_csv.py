import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from graph_csv import parse_attributes, read_case_texts, read_edges_csv, read_nodes_csv


class ParseAttributesTests(unittest.TestCase):
    def test_empty_string_returns_empty_dict(self):
        self.assertEqual(parse_attributes(""), {})

    def test_single_pair(self):
        self.assertEqual(parse_attributes("polarity=present"), {"polarity": "present"})

    def test_multiple_pairs(self):
        raw = "polarity=present; duration=3 days"
        self.assertEqual(parse_attributes(raw), {"polarity": "present", "duration": "3 days"})

    def test_value_containing_semicolon_is_not_split_early(self):
        raw = "evidence_text=Her pain resolved; she was discharged home; trigger=resolved; certainty=asserted"
        self.assertEqual(
            parse_attributes(raw),
            {
                "evidence_text": "Her pain resolved; she was discharged home",
                "trigger": "resolved",
                "certainty": "asserted",
            },
        )


class ReadCaseTextsTests(unittest.TestCase):
    def test_missing_file_returns_empty_dict(self):
        self.assertEqual(read_case_texts(Path("/nonexistent/case_texts.csv")), {})

    def test_reads_case_id_and_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "case_texts.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=("case_id", "case_text"))
                writer.writeheader()
                writer.writerow({"case_id": "CASE1", "case_text": "Texto, com vírgula."})
            self.assertEqual(read_case_texts(path), {"CASE1": "Texto, com vírgula."})


class ReadNodesEdgesCsvTests(unittest.TestCase):
    def test_read_nodes_csv_parses_attributes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "CASE1-nodes.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=("case_id", "node_id", "type", "label", "attributes")
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "case_id": "CASE1",
                        "node_id": "S1",
                        "type": "Symptom",
                        "label": "nausea",
                        "attributes": "polarity=present",
                    }
                )
            nodes = read_nodes_csv(path)
            self.assertEqual(
                nodes,
                [
                    {
                        "node_id": "S1",
                        "type": "Symptom",
                        "label": "nausea",
                        "attributes": {"polarity": "present"},
                    }
                ],
            )

    def test_read_edges_csv_parses_attributes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "CASE1-edges.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=("case_id", "edge_id", "source_id", "target_id", "relation", "attributes"),
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "case_id": "CASE1",
                        "edge_id": "e1",
                        "source_id": "P1",
                        "target_id": "S1",
                        "relation": "HAS_SYMPTOM",
                        "attributes": "evidence_text=she had nausea; char_start=10; char_end=20",
                    }
                )
            edges = read_edges_csv(path)
            self.assertEqual(
                edges,
                [
                    {
                        "edge_id": "e1",
                        "source_id": "P1",
                        "target_id": "S1",
                        "relation": "HAS_SYMPTOM",
                        "attributes": {
                            "evidence_text": "she had nausea",
                            "char_start": "10",
                            "char_end": "20",
                        },
                    }
                ],
            )


if __name__ == "__main__":
    unittest.main()
