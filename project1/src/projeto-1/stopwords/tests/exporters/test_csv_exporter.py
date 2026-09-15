import csv
import tempfile
import unittest
from pathlib import Path

from stopwords.case_reader import read_case
from stopwords.exporters.csv_exporter import export_pipeline_result
from stopwords.pipeline import process_case

_FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "cases.csv"


class ExportPipelineResultTests(unittest.TestCase):
    def test_writes_nodes_and_edges_csv_with_contract_columns(self):
        case = read_case(_FIXTURE, "PMC0000001_01")
        result = process_case(case)

        with tempfile.TemporaryDirectory() as tmp_dir:
            nodes_path, edges_path = export_pipeline_result(result, tmp_dir)
            self.assertTrue(nodes_path.exists())
            self.assertTrue(edges_path.exists())

            with nodes_path.open() as handle:
                header = next(csv.reader(handle))
            self.assertEqual(header, ["case_id", "node_id", "type", "label", "attributes"])

            with edges_path.open() as handle:
                header = next(csv.reader(handle))
            self.assertEqual(header, ["case_id", "edge_id", "source_id", "target_id", "relation", "attributes"])


if __name__ == "__main__":
    unittest.main()
