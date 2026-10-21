# -*- coding: utf-8 -*-
# LEGADO: primeira rota de montagem/avaliação da #29, substituída por
# src/montagem/montagem.py, src/dados/ e src/avaliacao/. Fora do pipeline final.
"""Testes unitarios para o gerenciador do gabarito ouro."""

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from project2.src.montagem.data.gold_manager import (
    GoldValidationError,
    consolidate_gold,
    generate_starter_packs,
    validate_case_annotation,
)


class TestGoldManager(unittest.TestCase):
    def setUp(self):
        self.case_id = "CASE_001"
        self.text = "The patient was diagnosed with acute pneumonia."
        self.df_entities = pd.DataFrame(
            [
                {
                    "case_id": "CASE_001",
                    "ent_id": "t1",
                    "char_start": 4,
                    "char_end": 11,
                    "texto": "patient",
                    "type": "Patient",
                    "concept_code": "",
                },
                {
                    "case_id": "CASE_001",
                    "ent_id": "t2",
                    "char_start": 31,
                    "char_end": 46,
                    "texto": "acute pneumonia",
                    "type": "Diagnosis",
                    "concept_code": "D011014",
                },
            ]
        )
        self.df_relations = pd.DataFrame(
            [
                {
                    "case_id": "CASE_001",
                    "source": "t1",
                    "target": "t2",
                    "relation": "DIAGNOSED_WITH",
                    "polarity": "present",
                    "certainty": "asserted",
                }
            ]
        )

    def test_validate_valid_case(self):
        rep = validate_case_annotation(
            self.case_id, self.df_entities, self.df_relations, self.text
        )
        self.assertEqual(rep["status"], "ok")
        self.assertEqual(len(rep["errors"]), 0)

    def test_validate_offset_mismatch(self):
        corrupted_ent = self.df_entities.copy()
        # Offset errado: 0 a 10 no texto é "The patien", não "patient"
        corrupted_ent.loc[0, "char_start"] = 0
        corrupted_ent.loc[0, "char_end"] = 10
        rep = validate_case_annotation(
            self.case_id, corrupted_ent, self.df_relations, self.text
        )
        self.assertEqual(rep["status"], "error")
        self.assertTrue(any("difere do trecho real" in err for err in rep["errors"]))

    def test_validate_missing_rel_reference(self):
        corrupted_rel = self.df_relations.copy()
        corrupted_rel.loc[0, "target"] = "t999"  # Não existe
        rep = validate_case_annotation(
            self.case_id, self.df_entities, corrupted_rel, self.text
        )
        self.assertEqual(rep["status"], "error")
        self.assertTrue(any("target 't999' nao existe" in err for err in rep["errors"]))

    def test_consolidate_gold_pipeline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            gold_dir = Path(tmpdir) / "gold"
            cases_dir = gold_dir / "cases" / self.case_id
            cases_dir.mkdir(parents=True)

            self.df_entities.to_csv(cases_dir / f"{self.case_id}-entities.csv", index=False)
            self.df_relations.to_csv(cases_dir / f"{self.case_id}-relations.csv", index=False)

            texts_file = Path(tmpdir) / "case_texts.csv"
            pd.DataFrame([{"case_id": self.case_id, "case_text": self.text}]).to_csv(
                texts_file, index=False
            )

            manifest = consolidate_gold(case_texts_path=texts_file, gold_dir=gold_dir)
            self.assertEqual(manifest["total_cases_consolidated"], 1)
            self.assertEqual(manifest["total_gold_entities"], 2)
            self.assertEqual(manifest["total_gold_relations"], 1)
            self.assertTrue((gold_dir / "gold_entidades.csv").exists())
            self.assertTrue((gold_dir / "gold_relacoes.csv").exists())


if __name__ == "__main__":
    unittest.main()
