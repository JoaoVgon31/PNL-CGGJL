# -*- coding: utf-8 -*-
"""Calculo formal de metricas de avaliacao para todas as estacoes do Projeto 2.

Padroniza as metricas da equipe (Regra 4 do planejamento):
  1. Entidades: Precision, Recall e F1 (casamento exato e relaxado por sobreposicao).
  2. Tipos e Conceitos: Acuracia, Macro/Micro-F1, Matriz de Confusao e acuracia MeSH.
  3. Relacoes e Negacao: Precision, Recall e F1 por relacao, avaliacao de polaridade
     (negacao) e certeza (hedging).
  4. Confronto Experimental: Calculo de deltas (P2 vs P1, com vs sem N-gramas).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support


def _safe_div(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator > 0 else 0.0


# ==============================================================================
# 1. Avaliacao de Entidades (Spans de Caracteres)
# ==============================================================================

def evaluate_entities(
    df_pred: pd.DataFrame,
    df_gold: pd.DataFrame,
    match_mode: str = "exact",
    require_same_type: bool = False,
) -> Dict[str, Any]:
    """Avalia o reconhecimento de entidades (spans) contra o gabarito.

    Args:
        df_pred: DataFrame contendo [case_id, char_start, char_end, (type)].
        df_gold: DataFrame contendo [case_id, char_start, char_end, (type)].
        match_mode: 'exact' (offsets identicos) ou 'overlap' (intersecao de caracteres).
        require_same_type: Se True, exige que o tipo predito seja igual ao do gabarito.

    Returns:
        Dicionario com TP, FP, FN, Precision, Recall e F1.
    """
    total_tp = 0
    total_pred = len(df_pred)
    total_gold = len(df_gold)

    # Agrupa por case_id
    cases = set(df_pred["case_id"].unique()) | set(df_gold["case_id"].unique())

    case_metrics = {}

    for cid in cases:
        p_case = df_pred[df_pred["case_id"] == cid].copy()
        g_case = df_gold[df_gold["case_id"] == cid].copy()

        matched_gold_indices = set()
        tp = 0

        for _, p_row in p_case.iterrows():
            p_start = int(p_row["char_start"])
            p_end = int(p_row["char_end"])
            p_type = str(p_row.get("type", "")).strip()

            best_match_idx = None
            best_overlap = 0

            for g_idx, g_row in g_case.iterrows():
                if g_idx in matched_gold_indices:
                    continue

                g_start = int(g_row["char_start"])
                g_end = int(g_row["char_end"])
                g_type = str(g_row.get("type", "")).strip()

                if require_same_type and p_type != g_type:
                    continue

                if match_mode == "exact":
                    if p_start == g_start and p_end == g_end:
                        best_match_idx = g_idx
                        break
                elif match_mode == "overlap":
                    inter_start = max(p_start, g_start)
                    inter_end = min(p_end, g_end)
                    if inter_start < inter_end:
                        overlap_len = inter_end - inter_start
                        if overlap_len > best_overlap:
                            best_overlap = overlap_len
                            best_match_idx = g_idx

            if best_match_idx is not None:
                tp += 1
                matched_gold_indices.add(best_match_idx)

        fp = len(p_case) - tp
        fn = len(g_case) - tp
        prec = _safe_div(tp, tp + fp)
        rec = _safe_div(tp, tp + fn)
        f1 = _safe_div(2 * prec * rec, prec + rec)

        case_metrics[cid] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": prec,
            "recall": rec,
            "f1": f1,
        }
        total_tp += tp

    total_fp = total_pred - total_tp
    total_fn = total_gold - total_tp

    precision = _safe_div(total_tp, total_tp + total_fp)
    recall = _safe_div(total_tp, total_tp + total_fn)
    f1 = _safe_div(2 * precision * recall, precision + recall)

    return {
        "match_mode": match_mode,
        "require_same_type": require_same_type,
        "total_predicted": total_pred,
        "total_gold": total_gold,
        "true_positives": total_tp,
        "false_positives": total_fp,
        "false_negatives": total_fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "by_case": case_metrics,
    }


# ==============================================================================
# 2. Avaliacao de Tipagem e Conceitos (Classificador e MeSH)
# ==============================================================================

def evaluate_types(
    df_pred: pd.DataFrame,
    df_gold: pd.DataFrame,
) -> Dict[str, Any]:
    """Avalia o desempenho da classificacao de tipos clinicos e vinculacao ao MeSH.

    Alinha predicoes com o gabarito atraves de (case_id, char_start, char_end)
    ou ent_id se disponivel.
    """
    # Alinhamento por (case_id, char_start, char_end)
    merged = pd.merge(
        df_pred,
        df_gold,
        on=["case_id", "char_start", "char_end"],
        suffixes=("_pred", "_gold"),
    )

    if merged.empty:
        # Tenta fallback por (case_id, ent_id)
        if "ent_id" in df_pred.columns and "ent_id" in df_gold.columns:
            merged = pd.merge(
                df_pred, df_gold, on=["case_id", "ent_id"], suffixes=("_pred", "_gold")
            )

    if merged.empty:
        return {
            "aligned_entities": 0,
            "accuracy": 0.0,
            "macro_f1": 0.0,
            "micro_f1": 0.0,
            "per_class": {},
            "confusion_matrix": {"labels": [], "matrix": []},
            "concept_link_accuracy": 0.0,
        }

    y_true = merged["type_gold"].fillna("UNKNOWN").astype(str).str.strip().tolist()
    y_pred = merged["type_pred"].fillna("UNKNOWN").astype(str).str.strip().tolist()

    # Classes presentes
    labels = sorted(list(set(y_true) | set(y_pred)))

    p_per_class, r_per_class, f1_per_class, support = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, zero_division=0
    )

    per_class_metrics = {}
    for i, lbl in enumerate(labels):
        per_class_metrics[lbl] = {
            "precision": float(p_per_class[i]),
            "recall": float(r_per_class[i]),
            "f1": float(f1_per_class[i]),
            "support": int(support[i]),
        }

    # Macro e Micro
    p_micro, r_micro, f1_micro, _ = precision_recall_fscore_support(
        y_true, y_pred, average="micro", zero_division=0
    )
    p_macro, r_macro, f1_macro, _ = precision_recall_fscore_support(
        y_true, y_pred, average="macro", zero_division=0
    )

    if len(labels) > 1:
        cm = confusion_matrix(y_true, y_pred, labels=labels).tolist()
    elif len(labels) == 1:
        cm = [[len(y_true)]]
    else:
        cm = []
    accuracy = float(np.mean([t == p for t, p in zip(y_true, y_pred)]))

    # Avaliacao de concept_code (MeSH)
    concept_acc = 0.0
    if "concept_code_gold" in merged.columns and "concept_code_pred" in merged.columns:
        valid_mesh_gold = merged[
            merged["concept_code_gold"].notna() & (merged["concept_code_gold"] != "")
        ]
        if not valid_mesh_gold.empty:
            matches = (
                valid_mesh_gold["concept_code_gold"].str.strip()
                == valid_mesh_gold["concept_code_pred"].astype(str).str.strip()
            ).sum()
            concept_acc = float(matches / len(valid_mesh_gold))

    return {
        "aligned_entities": len(merged),
        "accuracy": accuracy,
        "macro_precision": float(p_macro),
        "macro_recall": float(r_macro),
        "macro_f1": float(f1_macro),
        "micro_f1": float(f1_micro),
        "per_class": per_class_metrics,
        "confusion_matrix": {"labels": labels, "matrix": cm},
        "concept_link_accuracy": concept_acc,
    }


# ==============================================================================
# 3. Avaliacao de Relacoes Clinicas e Negacao
# ==============================================================================

def evaluate_relations(
    df_pred: pd.DataFrame,
    df_gold: pd.DataFrame,
) -> Dict[str, Any]:
    """Avalia a extracao de relacoes clinicas e classificacao de polaridade/certeza."""
    # Chave de ligacao: (case_id, source, target)
    p_keys = set(zip(df_pred["case_id"], df_pred["source"], df_pred["target"]))
    g_keys = set(zip(df_gold["case_id"], df_gold["source"], df_gold["target"]))

    total_pred = len(df_pred)
    total_gold = len(df_gold)

    merged = pd.merge(
        df_pred,
        df_gold,
        on=["case_id", "source", "target"],
        suffixes=("_pred", "_gold"),
    )

    if merged.empty:
        return {
            "total_predicted": total_pred,
            "total_gold": total_gold,
            "aligned_pairs": 0,
            "relation_precision": 0.0,
            "relation_recall": 0.0,
            "relation_f1": 0.0,
            "per_relation": {},
            "polarity_metrics": {"accuracy": 0.0, "negation_f1": 0.0},
            "certainty_metrics": {"accuracy": 0.0},
        }

    # Relacao correta quando par existe E tipo de relacao bate
    exact_rel_matches = (
        merged["relation_pred"].astype(str).str.strip()
        == merged["relation_gold"].astype(str).str.strip()
    ).sum()

    tp = int(exact_rel_matches)
    fp = total_pred - tp
    fn = total_gold - tp

    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = _safe_div(2 * precision * recall, precision + recall)

    # Metricas por tipo de relacao
    y_true_rel = merged["relation_gold"].astype(str).str.strip().tolist()
    y_pred_rel = merged["relation_pred"].astype(str).str.strip().tolist()
    rel_labels = sorted(list(set(y_true_rel) | set(y_pred_rel)))

    p_rel, r_rel, f1_rel, sup_rel = precision_recall_fscore_support(
        y_true_rel, y_pred_rel, labels=rel_labels, zero_division=0
    )

    per_relation = {}
    for i, lbl in enumerate(rel_labels):
        per_relation[lbl] = {
            "precision": float(p_rel[i]),
            "recall": float(r_rel[i]),
            "f1": float(f1_rel[i]),
            "support": int(sup_rel[i]),
        }

    # Avaliacao de Polaridade (Negacao: present vs absent)
    pol_acc = 0.0
    negation_f1 = 0.0
    if "polarity_gold" in merged.columns and "polarity_pred" in merged.columns:
        y_true_pol = merged["polarity_gold"].astype(str).str.strip()
        y_pred_pol = merged["polarity_pred"].astype(str).str.strip()
        pol_acc = float((y_true_pol == y_pred_pol).mean())

        # F1 especifico para a classe 'absent' (negação)
        _, _, f1_absent, _ = precision_recall_fscore_support(
            y_true_pol == "absent", y_pred_pol == "absent", average="binary", zero_division=0
        )
        negation_f1 = float(f1_absent)

    # Avaliacao de Certeza (Hedging: asserted vs hedged vs conditional)
    cert_acc = 0.0
    if "certainty_gold" in merged.columns and "certainty_pred" in merged.columns:
        y_true_cert = merged["certainty_gold"].astype(str).str.strip()
        y_pred_cert = merged["certainty_pred"].astype(str).str.strip()
        cert_acc = float((y_true_cert == y_pred_cert).mean())

    return {
        "total_predicted": total_pred,
        "total_gold": total_gold,
        "aligned_pairs": len(merged),
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "relation_precision": precision,
        "relation_recall": recall,
        "relation_f1": f1,
        "per_relation": per_relation,
        "polarity_metrics": {
            "overall_accuracy": pol_acc,
            "negation_f1": negation_f1,
        },
        "certainty_metrics": {
            "overall_accuracy": cert_acc,
        },
    }


# ==============================================================================
# 4. Confronto Experimental (Deltas P1 vs P2)
# ==============================================================================

def compare_experiments(
    metrics_baseline: Dict[str, Any],
    metrics_experiment: Dict[str, Any],
) -> Dict[str, Any]:
    """Calcula deltas percentuais entre o baseline (Projeto 1 / Sem N-grams) e o modelo novo."""
    comparison = {}
    keys = ["precision", "recall", "f1", "accuracy", "macro_f1", "micro_f1", "relation_f1"]

    for k in keys:
        b_val = metrics_baseline.get(k)
        e_val = metrics_experiment.get(k)
        if b_val is not None and e_val is not None:
            delta = float(e_val - b_val)
            pct_change = float((delta / b_val) * 100) if b_val > 0 else 0.0
            comparison[k] = {
                "baseline": float(b_val),
                "experiment": float(e_val),
                "delta": delta,
                "pct_change": pct_change,
            }

    return comparison
