# -*- coding: utf-8 -*-
"""Testes unitarios para o gerador de supervisao fraca."""

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from project2.src.montagem.data.weak_supervision import (
    WeakSupervisionGenerator,
    clean_entity_text_and_offsets,
    parse_attributes,
)


class MockToken:
    def __init__(self, text, start, end):
        self.text = text
        self.start = start
        self.end = end


class TestWeakSupervision(unittest.TestCase):
    def test_parse_attributes(self):
        raw = "code=D014057; preferred_term=Tomography; vocabulary=MeSH"
        parsed = parse_attributes(raw)
        self.assertEqual(parsed["code"], "D014057")
        self.assertEqual(parsed["preferred_term"], "Tomography")
        self.assertEqual(parsed["vocabulary"], "MeSH")

        self.assertEqual(parse_attributes(""), {})
        self.assertEqual(parse_attributes(None), {})

    def test_clean_entity_text_and_offsets(self):
        text = "A 44-year-old woman presented"
        tokens = [
            MockToken("A", 0, 1),
            MockToken("44-year-old", 2, 13),
            MockToken("woman", 14, 19),
        ]
        start, end, cleaned = clean_entity_text_and_offsets(tokens, text)
        self.assertEqual(start, 2)
        self.assertEqual(end, 19)
        self.assertEqual(cleaned, "44-year-old woman")

    def test_extract_case_data_real_case(self):
        gen = WeakSupervisionGenerator()
        df_texts = pd.read_csv("project1/data/case_texts.csv")
        sample_row = df_texts[df_texts["case_id"] == "PMC5137649_01"].iloc[0]

        data = gen.extract_case_data("PMC5137649_01", sample_row["case_text"])
        self.assertGreater(len(data["entities"]), 0)
        self.assertGreater(len(data["conll_sentences"]), 0)
        self.assertGreater(len(data["relations"]), 0)

        # Verifica alinhamento de offsets
        for ent in data["entities"][:10]:
            sub = sample_row["case_text"][ent["char_start"] : ent["char_end"]]
            self.assertEqual(sub, ent["texto"])

        # Verifica formato das sentenças CoNLL
        for sent in data["conll_sentences"][:3]:
            for tok, tag, bio_b, bio_t in sent:
                self.assertIn(bio_b[:2], ["O", "B-", "I-"])
                self.assertIn(bio_t[:2], ["O", "B-", "I-"])

    def test_generate_all_mini_pipeline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "silver"

            # Gera splits ficticios com 3 casos reais
            mini_splits_path = Path(tmpdir) / "splits.json"
            mini_splits = {
                "train": ["PMC5137649_01"],
                "val": ["PMC9387390_01"],
                "test": ["PMC10405809_01"],
            }
            mini_splits_path.write_text(json.dumps(mini_splits), encoding="utf-8")

            gen = WeakSupervisionGenerator(
                splits_path=mini_splits_path,
                output_dir=out_dir,
            )
            summary = gen.generate_all()

            self.assertTrue((out_dir / "silver_entidades_train.csv").exists())
            self.assertTrue((out_dir / "silver_entidades_tipadas_train.csv").exists())
            self.assertTrue((out_dir / "ner_train.conll").exists())
            self.assertTrue((out_dir / "silver_relacoes_train.csv").exists())
            self.assertTrue((out_dir / "entidades.csv").exists())
            self.assertTrue((out_dir / "relacoes.csv").exists())
            self.assertTrue((out_dir / "summary.json").exists())

            # Verifica integridade dos cabeçalhos
            df_ent = pd.read_csv(out_dir / "silver_entidades_train.csv")
            self.assertEqual(
                list(df_ent.columns),
                ["case_id", "ent_id", "char_start", "char_end", "texto"],
            )

            df_rel = pd.read_csv(out_dir / "silver_relacoes_train.csv")
            self.assertEqual(
                list(df_rel.columns),
                [
                    "case_id",
                    "source",
                    "target",
                    "relation",
                    "polarity",
                    "certainty",
                    "confianca",
                ],
            )


if __name__ == "__main__":
    unittest.main()
