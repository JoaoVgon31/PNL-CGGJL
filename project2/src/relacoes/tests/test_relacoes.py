# -*- coding: utf-8 -*-
"""Testes do modulo de relacoes (Etapa 4)."""

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from project2.src.relacoes.relacoes import (
    NON_PATIENT_MODELS,
    add_order_feature,
    apply_patient_rule,
    compare_all_configs,
    evaluate_against_gold,
    filter_non_patient_pairs,
    predict_relations,
    select_best_lr_config,
    train_config,
)


class TestApplyPatientRule(unittest.TestCase):
    def test_patient_as_source_maps_known_type(self):
        self.assertEqual(apply_patient_rule("Patient", "Symptom"), "HAS_SYMPTOM")
        self.assertEqual(apply_patient_rule("Patient", "History"), "HAS_HISTORY")
        self.assertEqual(apply_patient_rule("Patient", "Diagnosis"), "DIAGNOSED_WITH")
        self.assertEqual(apply_patient_rule("Patient", "Outcome"), "HAS_OUTCOME")
        self.assertEqual(apply_patient_rule("Patient", "Exam"), "UNDERWENT_EXAM")
        self.assertEqual(apply_patient_rule("Patient", "Medication"), "TREATED_WITH")
        self.assertEqual(apply_patient_rule("Patient", "Treatment"), "TREATED_WITH")
        self.assertEqual(apply_patient_rule("Patient", "Finding"), "HAS_FINDING")

    def test_patient_as_target_maps_symmetrically(self):
        self.assertEqual(apply_patient_rule("Symptom", "Patient"), "HAS_SYMPTOM")

    def test_patient_with_unknown_type_returns_none(self):
        self.assertIsNone(apply_patient_rule("Patient", "AnatomicalSite"))

    def test_no_patient_returns_none(self):
        self.assertIsNone(apply_patient_rule("Exam", "Finding"))
        self.assertIsNone(apply_patient_rule("Finding", "AnatomicalSite"))


class TestAddOrderFeature(unittest.TestCase):
    def test_marks_source_before_target(self):
        df_pairs = pd.DataFrame(
            [
                {"case_id": "C1", "source_id": "t1", "target_id": "t2"},
                {"case_id": "C1", "source_id": "t2", "target_id": "t1"},
            ]
        )
        df_entities = pd.DataFrame(
            [
                {"case_id": "C1", "ent_id": "t1", "char_start": 10},
                {"case_id": "C1", "ent_id": "t2", "char_start": 50},
            ]
        )
        result = add_order_feature(df_pairs, df_entities)
        self.assertEqual(result.loc[0, "source_before_target"], 1)
        self.assertEqual(result.loc[1, "source_before_target"], 0)

    def test_missing_entity_defaults_to_zero(self):
        df_pairs = pd.DataFrame(
            [{"case_id": "C1", "source_id": "t1", "target_id": "t_missing"}]
        )
        df_entities = pd.DataFrame(
            [{"case_id": "C1", "ent_id": "t1", "char_start": 10}]
        )
        result = add_order_feature(df_pairs, df_entities)
        self.assertEqual(result.loc[0, "source_before_target"], 0)
        self.assertNotIn("source_char_start", result.columns)
        self.assertNotIn("target_char_start", result.columns)


def _toy_training_frame() -> pd.DataFrame:
    rows = [
        {"case_id": "C1", "source_id": "e1", "target_id": "e2", "source_type": "Exam",
         "target_type": "Finding", "between_text": "revealed a mass in the",
         "distance_chars": 20, "relation": "REVEALS"},
        {"case_id": "C1", "source_id": "e3", "target_id": "e4", "source_type": "Finding",
         "target_type": "AnatomicalSite", "between_text": "located in the",
         "distance_chars": 15, "relation": "LOCATED_IN"},
        {"case_id": "C1", "source_id": "e5", "target_id": "e6", "source_type": "Exam",
         "target_type": "Finding", "between_text": "showed no abnormality in",
         "distance_chars": 25, "relation": "NONE"},
        {"case_id": "C1", "source_id": "e7", "target_id": "e8", "source_type": "Finding",
         "target_type": "AnatomicalSite", "between_text": "unrelated text between",
         "distance_chars": 30, "relation": "NONE"},
        {"case_id": "C1", "source_id": "e1", "target_id": "e9", "source_type": "Patient",
         "target_type": "Symptom", "between_text": "reported", "distance_chars": 5,
         "relation": "HAS_SYMPTOM"},
    ]
    df = pd.DataFrame(rows)
    entities = pd.DataFrame(
        [{"case_id": "C1", "ent_id": f"e{i}", "char_start": i * 10} for i in range(1, 10)]
    )
    return add_order_feature(df, entities)


class TestFilterNonPatientPairs(unittest.TestCase):
    def test_removes_rows_with_patient(self):
        df = _toy_training_frame()
        result = filter_non_patient_pairs(df)
        self.assertNotIn("Patient", result["source_type"].tolist())
        self.assertNotIn("Patient", result["target_type"].tolist())
        self.assertEqual(len(result), 4)


class TestTrainConfig(unittest.TestCase):
    def test_trains_and_returns_metrics(self):
        df = _toy_training_frame()
        pipeline, metrics = train_config(df, df, "logistic_regression", (1, 1))
        self.assertIn("per_relation", metrics)
        self.assertIn("confusion_matrix", metrics)
        self.assertIn("macro_f1_excluding_none", metrics)
        prediction = pipeline.predict(filter_non_patient_pairs(df))
        self.assertEqual(len(prediction), 4)


class TestCompareAllConfigs(unittest.TestCase):
    def test_returns_four_rows(self):
        df = _toy_training_frame()
        comparison = compare_all_configs(df, df)
        self.assertEqual(len(comparison), 4)
        self.assertSetEqual(
            set(comparison["model"]), {"logistic_regression", "linear_svm"}
        )
        self.assertSetEqual(set(comparison["ngram_range"]), {"1-1", "1-3"})


class TestSelectBestLrConfig(unittest.TestCase):
    def test_only_considers_logistic_regression(self):
        df = _toy_training_frame()
        ngram_range, pipeline, metrics = select_best_lr_config(df, df)
        self.assertIn(ngram_range, [(1, 1), (1, 3)])
        self.assertIsInstance(pipeline.named_steps["model"], type(
            NON_PATIENT_MODELS["logistic_regression"]()
        ))
        self.assertIn("macro_f1_excluding_none", metrics)


class TestPredictRelations(unittest.TestCase):
    def test_applies_rule_for_patient_pairs(self):
        df = _toy_training_frame()
        df["polarity"] = "present"
        df["certainty"] = "asserted"
        _, pipeline, _ = select_best_lr_config(df, df)

        result = predict_relations(df, pipeline)

        patient_row = result[(result["source"] == "e1") & (result["target"] == "e9")]
        self.assertEqual(len(patient_row), 1)
        self.assertEqual(patient_row.iloc[0]["relation"], "HAS_SYMPTOM")
        self.assertEqual(patient_row.iloc[0]["confidence"], 1.0)

    def test_output_columns_and_no_none(self):
        df = _toy_training_frame()
        df["polarity"] = "present"
        df["certainty"] = "asserted"
        _, pipeline, _ = select_best_lr_config(df, df)

        result = predict_relations(df, pipeline)

        self.assertListEqual(
            list(result.columns),
            ["case_id", "source", "target", "relation", "polarity", "certainty", "confidence"],
        )
        self.assertNotIn("NONE", result["relation"].tolist())


class TestEvaluateAgainstGold(unittest.TestCase):
    def test_evaluates_against_gold_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp) / "C1"
            case_dir.mkdir()
            gold_csv = case_dir / "C1-relations.csv"
            gold_csv.write_text(
                "case_id,source,target,relation,polarity,certainty\n"
                "C1,e1,e9,HAS_SYMPTOM,present,asserted\n"
            )

            df_pred = pd.DataFrame(
                [
                    {
                        "case_id": "C1", "source": "e1", "target": "e9",
                        "relation": "HAS_SYMPTOM", "polarity": "present",
                        "certainty": "asserted", "confidence": 1.0,
                    }
                ]
            )

            result = evaluate_against_gold(df_pred, ["C1"], gold_dir=Path(tmp))

        self.assertEqual(result["relation_f1"], 1.0)


if __name__ == "__main__":
    unittest.main()
