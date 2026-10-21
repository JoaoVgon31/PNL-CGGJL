# -*- coding: utf-8 -*-
# LEGADO: primeira rota de montagem/avaliação da #29, substituída por
# src/montagem/montagem.py, src/dados/ e src/avaliacao/. Fora do pipeline final.
"""Testes unitarios para o modulo de montagem e agrupamento de grafos."""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from project2.src.montagem.assembly.clustering import (
    HierarchicalMentionClusterer,
    extract_attributes_from_mention,
    normalize_label,
)
from project2.src.montagem.assembly.graph_builder import CaseGraphBuilder
from project2.src.montagem.assembly.pipeline import BatchGraphPipeline


class TestAssembly(unittest.TestCase):
    def test_normalize_label(self):
        self.assertEqual(normalize_label("the cyst"), "cyst")
        self.assertEqual(normalize_label("A 44-year-old woman"), "44-year-old woman")
        self.assertEqual(normalize_label("  pancreas. "), "pancreas")

    def test_extract_attributes_from_mention(self):
        cleaned, attrs = extract_attributes_from_mention("6cm cystic lesion")
        self.assertEqual(cleaned, "cystic lesion")
        self.assertEqual(attrs.get("size"), "6 cm")

        cleaned2, attrs2 = extract_attributes_from_mention("normal pancreas")
        self.assertEqual(cleaned2, "normal pancreas")
        self.assertEqual(attrs2, {})

    def test_clustering_merges_coreferent_mentions(self):
        clusterer = HierarchicalMentionClusterer()
        entities = [
            {"ent_id": "t1", "texto": "6cm cystic lesion", "type": "Finding", "polarity": "present"},
            {"ent_id": "t2", "texto": "the cyst", "type": "Finding", "polarity": "present"},
            {"ent_id": "t3", "texto": "normal pancreas", "type": "Finding", "polarity": "present"},
        ]
        clusters = clusterer.cluster_entities_of_same_type(entities)
        # Deve agrupar '6cm cystic lesion' e 'the cyst' no mesmo cluster, mantendo 'normal pancreas' separado
        self.assertEqual(len(clusters), 2)

        cyst_cluster = [c for c in clusters if "cystic lesion" in c["label"]][0]
        self.assertEqual(cyst_cluster["entity_ids"], ["t1", "t2"])
        self.assertEqual(cyst_cluster["attributes"]["size"], "6 cm")
        self.assertIn("mentions", cyst_cluster["attributes"])
        self.assertEqual(cyst_cluster["attributes"]["mentions"], "t1|t2")

    def test_case_graph_builder(self):
        builder = CaseGraphBuilder()
        df_ents = pd.DataFrame(
            [
                {"case_id": "C1", "ent_id": "t1", "texto": "contrast enhanced computed tomography", "type": "Exam", "concept_code": "D014057"},
                {"case_id": "C1", "ent_id": "t2", "texto": "6cm cystic lesion", "type": "Finding", "concept_code": ""},
                {"case_id": "C1", "ent_id": "t3", "texto": "stomach", "type": "AnatomicalSite", "concept_code": "ANAT001"},
                {"case_id": "C1", "ent_id": "t7", "texto": "the cyst", "type": "Finding", "concept_code": ""},
            ]
        )
        df_rels = pd.DataFrame(
            [
                {"case_id": "C1", "source": "t1", "target": "t2", "relation": "REVEALS", "certainty": "asserted", "trigger": "demonstrating"},
                {"case_id": "C1", "source": "t2", "target": "t3", "relation": "LOCATED_IN", "certainty": "asserted", "trigger": "between the"},
            ]
        )

        df_nodes, df_edges = builder.build_case_graph("C1", df_ents, df_rels)

        # Verifica nos clinicos e conceitos
        self.assertIn("node_id", df_nodes.columns)
        self.assertIn("label", df_nodes.columns)
        self.assertIn("attributes", df_nodes.columns)

        # t2 e t7 foram fundidos em 1 no Finding
        finding_nodes = df_nodes[df_nodes["type"] == "Finding"]
        self.assertEqual(len(finding_nodes), 1)
        self.assertIn("size=6 cm", finding_nodes.iloc[0]["attributes"])
        self.assertIn("mentions=t2|t7", finding_nodes.iloc[0]["attributes"])

        # Concept nodes gerados para Exam (D014057) e AnatomicalSite (ANAT001)
        concept_nodes = df_nodes[df_nodes["type"] == "Concept"]
        self.assertEqual(len(concept_nodes), 2)

        # Arestas SAME_AS geradas
        same_as_edges = df_edges[df_edges["relation"] == "SAME_AS"]
        self.assertEqual(len(same_as_edges), 2)

        # Arestas clinicas mapeadas para node_ids
        reveals_edges = df_edges[df_edges["relation"] == "REVEALS"]
        self.assertEqual(len(reveals_edges), 1)
        self.assertEqual(reveals_edges.iloc[0]["source_id"], "E1")
        self.assertEqual(reveals_edges.iloc[0]["target_id"], finding_nodes.iloc[0]["node_id"])

    def test_batch_pipeline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "processed"
            ent_file = Path(tmpdir) / "entidades_tipadas.csv"
            rel_file = Path(tmpdir) / "relacoes.csv"

            pd.DataFrame(
                [
                    {"case_id": "C1", "ent_id": "t1", "texto": "fever", "type": "Symptom", "concept_code": "D005334"},
                ]
            ).to_csv(ent_file, index=False)

            pd.DataFrame(
                [
                    {"case_id": "C1", "source": "t1", "target": "t1", "relation": "NONE"},
                ]
            ).to_csv(rel_file, index=False)

            pipeline = BatchGraphPipeline(
                entities_path=ent_file,
                relations_path=rel_file,
                output_dir=out_dir,
            )
            df_summary = pipeline.run()

            self.assertTrue((out_dir / "C1-nodes.csv").exists())
            self.assertTrue((out_dir / "C1-edges.csv").exists())
            self.assertTrue((out_dir / "_resumo.csv").exists())
            self.assertEqual(len(df_summary), 1)
            self.assertEqual(df_summary.iloc[0]["status"], "ok")


if __name__ == "__main__":
    unittest.main()
