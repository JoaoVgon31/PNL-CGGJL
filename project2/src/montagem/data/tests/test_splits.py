# -*- coding: utf-8 -*-
# LEGADO: primeira rota de montagem/avaliação da #29, substituída por
# src/montagem/montagem.py, src/dados/ e src/avaliacao/. Fora do pipeline final.
"""Testes unitarios para o modulo de splits."""

import json
import tempfile
import unittest
from pathlib import Path

from project2.src.montagem.data.splits import create_case_splits, load_splits, save_splits


class TestSplits(unittest.TestCase):
    def setUp(self):
        self.mock_cases = [f"CASE_{i:03d}" for i in range(56)]

    def test_create_case_splits_counts(self):
        splits = create_case_splits(self.mock_cases, train_count=40, val_count=8, test_count=8, random_state=42)
        self.assertEqual(len(splits["train"]), 40)
        self.assertEqual(len(splits["val"]), 8)
        self.assertEqual(len(splits["test"]), 8)
        self.assertEqual(splits["metadata"]["total_cases"], 56)

    def test_no_data_leakage(self):
        splits = create_case_splits(self.mock_cases, train_count=40, val_count=8, test_count=8, random_state=42)
        train_set = set(splits["train"])
        val_set = set(splits["val"])
        test_set = set(splits["test"])

        self.assertTrue(train_set.isdisjoint(val_set))
        self.assertTrue(train_set.isdisjoint(test_set))
        self.assertTrue(val_set.isdisjoint(test_set))
        self.assertEqual(train_set | val_set | test_set, set(self.mock_cases))

    def test_reproducibility(self):
        s1 = create_case_splits(self.mock_cases, train_count=40, val_count=8, test_count=8, random_state=42)
        s2 = create_case_splits(self.mock_cases, train_count=40, val_count=8, test_count=8, random_state=42)
        self.assertEqual(s1["train"], s2["train"])
        self.assertEqual(s1["val"], s2["val"])
        self.assertEqual(s1["test"], s2["test"])

    def test_invalid_counts_raise(self):
        with self.assertRaises(ValueError):
            create_case_splits(self.mock_cases, train_count=30, val_count=10, test_count=5)

    def test_save_and_load_splits(self):
        splits = create_case_splits(self.mock_cases, train_count=40, val_count=8, test_count=8, random_state=42)
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir) / "splits.json"
            save_splits(splits, tmp_path)
            self.assertTrue(tmp_path.exists())

            loaded = load_splits(tmp_path)
            self.assertEqual(loaded["train"], splits["train"])
            self.assertEqual(loaded["val"], splits["val"])
            self.assertEqual(loaded["test"], splits["test"])


if __name__ == "__main__":
    unittest.main()
