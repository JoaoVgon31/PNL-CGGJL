# -*- coding: utf-8 -*-
"""Testes unitarios para o modulo de metricas de avaliacao."""

import unittest
import pandas as pd

from project2.src.montagem.evaluation.metrics import (
    compare_experiments,
    evaluate_entities,
    evaluate_relations,
    evaluate_types,
)


class TestMetrics(unittest.TestCase):
    def setUp(self):
        # Entidades Gold
        self.df_gold_ent = pd.DataFrame(
            [
                {"case_id": "C1", "ent_id": "t1", "char_start": 0, "char_end": 10, "type": "Exam", "concept_code": "D001"},
                {"case_id": "C1", "ent_id": "t2", "char_start": 20, "char_end": 35, "type": "Finding", "concept_code": "D002"},
                {"case_id": "C1", "ent_id": "t3", "char_start": 40, "char_end": 50, "type": "Symptom", "concept_code": ""},
            ]
        )

        # Entidades Preditas: t1 bate exato, t2 tem overlap parcial (20:30 em vez de 20:35), t4 é falso positivo
        self.df_pred_ent = pd.DataFrame(
            [
                {"case_id": "C1", "ent_id": "p1", "char_start": 0, "char_end": 10, "type": "Exam", "concept_code": "D001"},
                {"case_id": "C1", "ent_id": "p2", "char_start": 20, "char_end": 30, "type": "Finding", "concept_code": "D002"},
                {"case_id": "C1", "ent_id": "p4", "char_start": 60, "char_end": 70, "type": "Exam", "concept_code": ""},
            ]
        )

        # Relacoes Gold
        self.df_gold_rel = pd.DataFrame(
            [
                {"case_id": "C1", "source": "t1", "target": "t2", "relation": "REVEALS", "polarity": "present", "certainty": "asserted"},
                {"case_id": "C1", "source": "t2", "target": "t3", "relation": "LOCATED_IN", "polarity": "absent", "certainty": "asserted"},
            ]
        )

        # Relacoes Preditas: primeira bate perfeitamente, segunda tem relacao errada e polaridade errada
        self.df_pred_rel = pd.DataFrame(
            [
                {"case_id": "C1", "source": "t1", "target": "t2", "relation": "REVEALS", "polarity": "present", "certainty": "asserted"},
                {"case_id": "C1", "source": "t2", "target": "t3", "relation": "HAS_FINDING", "polarity": "present", "certainty": "asserted"},
            ]
        )

    def test_evaluate_entities_exact(self):
        res = evaluate_entities(self.df_pred_ent, self.df_gold_ent, match_mode="exact")
        # Apenas t1 bate exato
        self.assertEqual(res["true_positives"], 1)
        self.assertEqual(res["false_positives"], 2)
        self.assertEqual(res["false_negatives"], 2)
        self.assertAlmostEqual(res["precision"], 1 / 3)
        self.assertAlmostEqual(res["recall"], 1 / 3)
        self.assertAlmostEqual(res["f1"], 1 / 3)

    def test_evaluate_entities_overlap(self):
        res = evaluate_entities(self.df_pred_ent, self.df_gold_ent, match_mode="overlap")
        # t1 e t2 batem com overlap
        self.assertEqual(res["true_positives"], 2)
        self.assertEqual(res["false_positives"], 1)
        self.assertEqual(res["false_negatives"], 1)
        self.assertAlmostEqual(res["precision"], 2 / 3)
        self.assertAlmostEqual(res["recall"], 2 / 3)
        self.assertAlmostEqual(res["f1"], 2 / 3)

    def test_evaluate_types(self):
        # Avalia sobre entidades alinhadas exatas
        res = evaluate_types(self.df_pred_ent, self.df_gold_ent)
        self.assertEqual(res["aligned_entities"], 1)  # Apenas p1/t1 bateu offsets exatos
        self.assertEqual(res["accuracy"], 1.0)
        self.assertEqual(res["concept_link_accuracy"], 1.0)

    def test_evaluate_relations(self):
        res = evaluate_relations(self.df_pred_rel, self.df_gold_rel)
        # Primeira relacao bateu exato (REVEALS)
        self.assertEqual(res["true_positives"], 1)
        self.assertEqual(res["false_positives"], 1)
        self.assertEqual(res["false_negatives"], 1)
        self.assertAlmostEqual(res["relation_f1"], 0.5)

        # Polaridade: 1 de 2 bateu ('present')
        self.assertAlmostEqual(res["polarity_metrics"]["overall_accuracy"], 0.5)
        # Negação ('absent'): pred falhou em detectar 'absent' no segundo par -> F1 = 0.0
        self.assertEqual(res["polarity_metrics"]["negation_f1"], 0.0)

    def test_compare_experiments(self):
        baseline = {"f1": 0.60, "precision": 0.70, "recall": 0.50}
        experiment = {"f1": 0.75, "precision": 0.80, "recall": 0.70}
        comp = compare_experiments(baseline, experiment)

        self.assertAlmostEqual(comp["f1"]["delta"], 0.15)
        self.assertAlmostEqual(comp["f1"]["pct_change"], 25.0)


if __name__ == "__main__":
    unittest.main()
