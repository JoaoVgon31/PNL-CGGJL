import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from export_graph_data import build_case_payload, build_manifest, discover_cases, export_all
from graph_csv import EDGE_COLUMNS, NODE_COLUMNS


def _write_csv(path: Path, columns: tuple, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _write_case_graph(directory: Path, case_id: str) -> None:
    _write_csv(
        directory / f"{case_id}-nodes.csv",
        NODE_COLUMNS,
        [{"case_id": case_id, "node_id": "P1", "type": "Patient", "label": "case", "attributes": ""}],
    )
    _write_csv(directory / f"{case_id}-edges.csv", EDGE_COLUMNS, [])


class DiscoverCasesTests(unittest.TestCase):
    def test_finds_cases_across_available_sources_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_case_graph(root / "data" / "processed", "CASE1")
            _write_case_graph(root / "src" / "stopwords" / "output", "CASE1")
            _write_case_graph(root / "src" / "stopwords" / "output", "CASE2")
            # src/sintagmas/output nem existe -- não deve quebrar a varredura.

            cases = discover_cases(root)

            self.assertEqual(set(cases.keys()), {"CASE1", "CASE2"})
            self.assertEqual(set(cases["CASE1"].keys()), {"combinado", "stopwords"})
            self.assertEqual(set(cases["CASE2"].keys()), {"stopwords"})

    def test_ignores_nodes_csv_without_matching_edges_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = root / "src" / "tokenizacao" / "output"
            directory.mkdir(parents=True)
            _write_csv(
                directory / "CASE1-nodes.csv",
                NODE_COLUMNS,
                [{"case_id": "CASE1", "node_id": "P1", "type": "Patient", "label": "x", "attributes": ""}],
            )
            # sem CASE1-edges.csv

            cases = discover_cases(root)

            self.assertEqual(cases, {})


class BuildCasePayloadTests(unittest.TestCase):
    def test_includes_case_text_when_known(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _write_case_graph(directory, "CASE1")
            sources = {"combinado": directory}

            payload = build_case_payload("CASE1", sources, {"CASE1": "texto do caso"})

            self.assertEqual(payload["case_text"], "texto do caso")
            self.assertEqual(list(payload["graphs"].keys()), ["combinado"])

    def test_omits_case_text_when_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _write_case_graph(directory, "CASE1")
            sources = {"combinado": directory}

            payload = build_case_payload("CASE1", sources, {})

            self.assertNotIn("case_text", payload)


class BuildManifestTests(unittest.TestCase):
    def test_lists_cases_sorted_with_their_graph_keys(self):
        payloads = {
            "CASE2": {"graphs": {"stopwords": {}}},
            "CASE1": {"graphs": {"combinado": {}, "stopwords": {}}},
        }

        manifest = build_manifest(payloads)

        self.assertEqual(
            manifest,
            {
                "cases": [
                    {"case_id": "CASE1", "graphs": ["combinado", "stopwords"]},
                    {"case_id": "CASE2", "graphs": ["stopwords"]},
                ]
            },
        )


class ExportAllTests(unittest.TestCase):
    def test_writes_case_files_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_case_graph(root / "data" / "processed", "CASE1")
            _write_case_graph(root / "src" / "stopwords" / "output", "CASE1")
            _write_case_graph(root / "src" / "stopwords" / "output", "CASE2")
            _write_csv(
                root / "data" / "case_texts.csv",
                ("case_id", "case_text"),
                [{"case_id": "CASE1", "case_text": "texto do CASE1"}],
            )
            output_dir = root / "visualizer" / "data"

            manifest = export_all(root, output_dir)

            self.assertEqual(
                manifest,
                {
                    "cases": [
                        {"case_id": "CASE1", "graphs": ["combinado", "stopwords"]},
                        {"case_id": "CASE2", "graphs": ["stopwords"]},
                    ]
                },
            )
            self.assertEqual(json.loads((output_dir / "manifest.json").read_text()), manifest)

            case1 = json.loads((output_dir / "CASE1.json").read_text())
            self.assertEqual(case1["case_text"], "texto do CASE1")
            self.assertEqual(set(case1["graphs"].keys()), {"combinado", "stopwords"})

            case2 = json.loads((output_dir / "CASE2.json").read_text())
            self.assertNotIn("case_text", case2)


if __name__ == "__main__":
    unittest.main()
