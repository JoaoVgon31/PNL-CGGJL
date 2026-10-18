# -*- coding: utf-8 -*-
"""Etapa 4 do Projeto 2: relacoes entre entidades clinicas.

Combina uma regra fixa para pares envolvendo o paciente com um
classificador de N-gramas para os demais pares de entidades.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MaxAbsScaler, OneHotEncoder
from sklearn.svm import LinearSVC

from project2.src.evaluation.metrics import evaluate_relations

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ENTIDADES = REPO_ROOT / "project2" / "data" / "mock" / "relacoes" / "entidades.csv"
DEFAULT_GOLD_DIR = REPO_ROOT / "project2" / "data" / "gold" / "cases"
DEFAULT_TRAIN = REPO_ROOT / "project2" / "data" / "mock" / "relacoes" / "train.csv"
DEFAULT_VAL = REPO_ROOT / "project2" / "data" / "mock" / "relacoes" / "val.csv"
DEFAULT_TEST = REPO_ROOT / "project2" / "data" / "mock" / "relacoes" / "test.csv"
DEFAULT_OUTPUT = REPO_ROOT / "project2" / "data" / "relacoes.csv"
DEFAULT_RESULTADOS = REPO_ROOT / "project2" / "data" / "resultados" / "relacoes.csv"

PATIENT_RELATION_MAP: Dict[str, str] = {
    "Symptom": "HAS_SYMPTOM",
    "History": "HAS_HISTORY",
    "Diagnosis": "DIAGNOSED_WITH",
    "Outcome": "HAS_OUTCOME",
    "Exam": "UNDERWENT_EXAM",
    "Medication": "TREATED_WITH",
    "Treatment": "TREATED_WITH",
    "Finding": "HAS_FINDING",
}


def apply_patient_rule(source_type: str, target_type: str) -> Optional[str]:
    """Retorna a relacao fixa quando um dos tipos e 'Patient', senao None.

    O par (Patient, tipo) sempre produz a mesma relacao, independente de
    contexto textual - nao precisa de classificador.
    """
    if source_type == "Patient":
        return PATIENT_RELATION_MAP.get(target_type)
    if target_type == "Patient":
        return PATIENT_RELATION_MAP.get(source_type)
    return None


def load_entities(entidades_path: Path = DEFAULT_ENTIDADES) -> pd.DataFrame:
    """Carrega case_id, ent_id e char_start das entidades (Etapa 2/5)."""
    return pd.read_csv(entidades_path, usecols=["case_id", "ent_id", "char_start"])


def add_order_feature(df_pairs: pd.DataFrame, df_entities: pd.DataFrame) -> pd.DataFrame:
    """Adiciona 'source_before_target' (0/1) via join com char_start.

    distance_chars e between_text sao simetricos (calculados com min/max),
    entao a ordem textual so pode ser recuperada juntando pelos ent_id.
    """
    source_starts = df_entities.rename(
        columns={"ent_id": "source_id", "char_start": "source_char_start"}
    )
    target_starts = df_entities.rename(
        columns={"ent_id": "target_id", "char_start": "target_char_start"}
    )

    df = df_pairs.merge(source_starts, on=["case_id", "source_id"], how="left")
    df = df.merge(target_starts, on=["case_id", "target_id"], how="left")

    df["source_before_target"] = (
        (df["source_char_start"] < df["target_char_start"]).fillna(False).astype(int)
    )
    return df.drop(columns=["source_char_start", "target_char_start"])


NON_PATIENT_MODELS: Dict[str, Callable[[], BaseEstimator]] = {
    "logistic_regression": lambda: LogisticRegression(
        max_iter=1000, class_weight="balanced", random_state=42
    ),
    "linear_svm": lambda: LinearSVC(class_weight="balanced", random_state=42),
}


def filter_non_patient_pairs(df: pd.DataFrame) -> pd.DataFrame:
    """Remove pares onde origem ou destino e 'Patient' (resolvidos por regra)."""
    mask = (df["source_type"] != "Patient") & (df["target_type"] != "Patient")
    return df[mask].reset_index(drop=True)


def build_feature_pipeline(ngram_range: Tuple[int, int], model: BaseEstimator) -> Pipeline:
    """Monta o pipeline de features (TF-IDF + tipos + distancia + ordem) + modelo."""
    preprocessor = ColumnTransformer(
        transformers=[
            ("between_text", TfidfVectorizer(ngram_range=ngram_range), "between_text"),
            ("types", OneHotEncoder(handle_unknown="ignore"), ["source_type", "target_type"]),
            ("numeric", MaxAbsScaler(), ["distance_chars", "source_before_target"]),
        ]
    )
    return Pipeline([("features", preprocessor), ("model", model)])


def compute_relation_metrics(y_true: List[str], y_pred: List[str], labels: List[str]) -> Dict:
    """Calcula precision/recall/F1 por relacao, matriz de confusao e macro-F1 sem NONE.

    macro_f1_excluding_none e a media do F1 apenas dos labels != "NONE" que
    tem suporte > 0 (presentes de fato em y_true) - labels so vistos em
    treino (support=0 em y_true/y_pred) nao devem arrastar a media para
    baixo artificialmente. per_relation e confusion_matrix continuam
    cobrindo todos os labels recebidos.
    """
    precision, recall, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, zero_division=0
    )
    cm = confusion_matrix(y_true, y_pred, labels=labels).tolist()
    per_relation = {
        lbl: {
            "precision": float(precision[i]),
            "recall": float(recall[i]),
            "f1": float(f1[i]),
            "support": int(support[i]),
        }
        for i, lbl in enumerate(labels)
    }
    non_none_f1 = [
        per_relation[lbl]["f1"]
        for lbl in labels
        if lbl != "NONE" and per_relation[lbl]["support"] > 0
    ]
    macro_f1_excluding_none = float(np.mean(non_none_f1)) if non_none_f1 else 0.0
    return {
        "per_relation": per_relation,
        "confusion_matrix": {"labels": labels, "matrix": cm},
        "macro_f1_excluding_none": macro_f1_excluding_none,
    }


def train_config(
    df_train: pd.DataFrame,
    df_val: pd.DataFrame,
    model_name: str,
    ngram_range: Tuple[int, int],
) -> Tuple[Pipeline, Dict]:
    """Treina uma combinacao (modelo, ngram_range) nos pares sem Patient."""
    df_train_np = filter_non_patient_pairs(df_train)
    df_val_np = filter_non_patient_pairs(df_val)

    model = NON_PATIENT_MODELS[model_name]()
    pipeline = build_feature_pipeline(ngram_range, model)
    pipeline.fit(df_train_np, df_train_np["relation"])

    y_pred = pipeline.predict(df_val_np)
    labels = sorted(set(df_train_np["relation"]) | set(df_val_np["relation"]) | set(y_pred))
    metrics = compute_relation_metrics(df_val_np["relation"].tolist(), list(y_pred), labels)
    return pipeline, metrics


GRID: List[Tuple[str, Tuple[int, int]]] = [
    ("logistic_regression", (1, 1)),
    ("logistic_regression", (1, 3)),
    ("linear_svm", (1, 1)),
    ("linear_svm", (1, 3)),
]


def compare_all_configs(df_train: pd.DataFrame, df_val: pd.DataFrame) -> pd.DataFrame:
    """Treina as 4 combinacoes do grid e monta a tabela comparativa."""
    rows = []
    for model_name, ngram_range in GRID:
        _, metrics = train_config(df_train, df_val, model_name, ngram_range)
        rows.append(
            {
                "model": model_name,
                "ngram_range": f"{ngram_range[0]}-{ngram_range[1]}",
                "macro_f1_excluding_none": metrics["macro_f1_excluding_none"],
                "confusion_matrix": json.dumps(metrics["confusion_matrix"]),
                "per_relation": json.dumps(metrics["per_relation"]),
            }
        )
    return pd.DataFrame(rows)


def select_best_lr_config(
    df_train: pd.DataFrame, df_val: pd.DataFrame
) -> Tuple[Tuple[int, int], Pipeline, Dict]:
    """Escolhe, entre unigrama e 1-3-grama, a config de LogisticRegression com
    melhor macro-F1 (sem NONE) em validacao. LR e sempre o modelo de producao
    porque fornece predict_proba nativo (ver spec, secao de confianca)."""
    best_score = -1.0
    best: Tuple[Tuple[int, int], Pipeline, Dict] = ((1, 1), None, {})
    for ngram_range in [(1, 1), (1, 3)]:
        pipeline, metrics = train_config(df_train, df_val, "logistic_regression", ngram_range)
        score = metrics["macro_f1_excluding_none"]
        if score > best_score:
            best_score = score
            best = (ngram_range, pipeline, metrics)
    return best


def predict_relations(df_candidates: pd.DataFrame, pipeline: Pipeline) -> pd.DataFrame:
    """Aplica a regra de Patient e o classificador aos demais pares.

    Descarta linhas preditas como NONE e formata no contrato de saida
    (case_id, source, target, relation, polarity, certainty, confidence)
    esperado por project2/src/evaluation/metrics.py:evaluate_relations.

    Pre-condicao: df_candidates ja deve ter passado por prepare_features
    antes de chegar aqui (colunas source_type/target_type/between_text
    sem nulos e coluna source_before_target presente). Esta funcao nao
    chama prepare_features automaticamente para nao alterar o contrato
    de quem ja faz essa preparacao antes de chamar (ex.: generate_outputs).
    """
    df = df_candidates.copy()

    rule_relation = [
        apply_patient_rule(s, t) for s, t in zip(df["source_type"], df["target_type"])
    ]
    df = df.assign(rule_relation=rule_relation)

    is_rule = df["rule_relation"].notna()
    df_rule = df[is_rule].copy()
    df_rule["relation"] = df_rule["rule_relation"]
    df_rule["confidence"] = 1.0

    df_ml = df[~is_rule].copy()
    if not df_ml.empty:
        proba = pipeline.predict_proba(df_ml)
        classes = pipeline.named_steps["model"].classes_
        pred_idx = proba.argmax(axis=1)
        df_ml["relation"] = [classes[i] for i in pred_idx]
        df_ml["confidence"] = proba.max(axis=1)

    combined = pd.concat([df_rule, df_ml], ignore_index=True)
    combined = combined[combined["relation"] != "NONE"].copy()
    combined = combined.rename(columns={"source_id": "source", "target_id": "target"})

    return combined[
        ["case_id", "source", "target", "relation", "polarity", "certainty", "confidence"]
    ].reset_index(drop=True)


def load_gold_relations(case_id: str, gold_dir: Path = DEFAULT_GOLD_DIR) -> pd.DataFrame:
    """Carrega o gabarito manual de relacoes de um caso anotado."""
    path = gold_dir / case_id / f"{case_id}-relations.csv"
    return pd.read_csv(path)


def evaluate_against_gold(
    df_pred: pd.DataFrame,
    case_ids: List[str],
    gold_dir: Path = DEFAULT_GOLD_DIR,
) -> Dict:
    """Avalia predicoes contra o gabarito manual dos casos indicados.

    Mesma assinatura de entrada/saida de evaluate_relations, para plugar
    direto quando os casos-gabarito (ex.: PMC4630775_01, PMC6083636_03)
    forem anotados a mao.
    """
    gold_frames = [load_gold_relations(cid, gold_dir) for cid in case_ids]
    df_gold = pd.concat(gold_frames, ignore_index=True)
    df_pred_subset = df_pred[df_pred["case_id"].isin(case_ids)]
    return evaluate_relations(df_pred_subset, df_gold)


def prepare_features(df: pd.DataFrame, df_entities: pd.DataFrame) -> pd.DataFrame:
    """Preenche nulos de tipo/texto e adiciona 'source_before_target'.

    Pre-condicao exigida por predict_relations: qualquer df_candidates
    passado a ela deve ter passado por esta funcao antes (colunas
    source_type/target_type/between_text sem nulos e coluna
    source_before_target presente).
    """
    df = df.copy()
    df["source_type"] = df["source_type"].fillna("UNKNOWN")
    df["target_type"] = df["target_type"].fillna("UNKNOWN")
    df["between_text"] = df["between_text"].fillna("")
    return add_order_feature(df, df_entities)


def generate_outputs(
    train_path: Path = DEFAULT_TRAIN,
    val_path: Path = DEFAULT_VAL,
    test_path: Path = DEFAULT_TEST,
    entidades_path: Path = DEFAULT_ENTIDADES,
    output_path: Path = DEFAULT_OUTPUT,
    resultados_path: Path = DEFAULT_RESULTADOS,
) -> None:
    """Treina, compara as 4 configuracoes (em val) e gera relacoes.csv +
    resultados/relacoes.csv (grid em val + linha final da config vencedora
    avaliada em test)."""
    df_entities = load_entities(entidades_path)
    df_train = prepare_features(pd.read_csv(train_path), df_entities)
    df_val = prepare_features(pd.read_csv(val_path), df_entities)
    df_test = prepare_features(pd.read_csv(test_path), df_entities)

    comparison = compare_all_configs(df_train, df_val)
    comparison["split"] = "val"

    best_ngram_range, best_pipeline, _ = select_best_lr_config(df_train, df_val)
    _, test_metrics = train_config(df_train, df_test, "logistic_regression", best_ngram_range)
    test_row = pd.DataFrame(
        [
            {
                "model": "logistic_regression",
                "ngram_range": f"{best_ngram_range[0]}-{best_ngram_range[1]}",
                "macro_f1_excluding_none": test_metrics["macro_f1_excluding_none"],
                "confusion_matrix": json.dumps(test_metrics["confusion_matrix"]),
                "per_relation": json.dumps(test_metrics["per_relation"]),
                "split": "test",
            }
        ]
    )
    comparison = pd.concat([comparison, test_row], ignore_index=True)

    resultados_path.parent.mkdir(parents=True, exist_ok=True)
    comparison.to_csv(resultados_path, index=False)

    predictions = predict_relations(df_test, best_pipeline)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(output_path, index=False)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Etapa 4: relacoes entre entidades")
    parser.add_argument("--train", type=Path, default=DEFAULT_TRAIN)
    parser.add_argument("--val", type=Path, default=DEFAULT_VAL)
    parser.add_argument("--test", type=Path, default=DEFAULT_TEST)
    parser.add_argument("--entidades", type=Path, default=DEFAULT_ENTIDADES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--resultados", type=Path, default=DEFAULT_RESULTADOS)
    args = parser.parse_args()
    generate_outputs(
        args.train, args.val, args.test, args.entidades, args.output, args.resultados
    )
