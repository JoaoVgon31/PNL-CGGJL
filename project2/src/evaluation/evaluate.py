# -*- coding: utf-8 -*-
"""Script unificado de avaliacao oficial para toda a equipe do Projeto 2.

Uso:
  # Avaliar deteccao de entidades (Estacao 2 - Caio)
  python -m project2.src.evaluation.evaluate --task entities --pred entidades.csv --gold gold_entidades.csv

  # Avaliar classificacao de tipos e MeSH (Estacao 3 - Lucas)
  python -m project2.src.evaluation.evaluate --task types --pred entidades_tipadas.csv --gold gold_entidades.csv

  # Avaliar extracao de relacoes e negacao (Estacao 4 - Joao)
  python -m project2.src.evaluation.evaluate --task relations --pred relacoes.csv --gold gold_relacoes.csv

  # Confronto Experimental: Comparar P2 vs P1 (Regra 5)
  python -m project2.src.evaluation.evaluate --task entities --pred entidades_p2.csv --baseline entidades_p1.csv --gold gold_entidades.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# Garante suporte UTF-8 no terminal Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd

from project2.src.evaluation.metrics import (
    compare_experiments,
    evaluate_entities,
    evaluate_relations,
    evaluate_types,
)

DEFAULT_GOLD_DIR = Path("project2/data/gold")


def _format_table_row(col1: str, col2: str, col3: str, col4: str, w: int = 15) -> str:
    return f"{col1:<{w}} | {col2:<{w}} | {col3:<{w}} | {col4:<{w}}"


def print_entities_report(metrics: Dict[str, Any]):
    print("\n" + "=" * 65)
    print("RELATORIO OFICIAL DE AVALIACAO - ENTIDADES (Estacao 2)")
    print("=" * 65)
    print(f"Modo de Casamento:    {metrics['match_mode'].upper()}")
    print(f"Exige mesmo tipo:     {metrics['require_same_type']}")
    print(f"Total Predito:        {metrics['total_predicted']}")
    print(f"Total Gabarito:       {metrics['total_gold']}")
    print(f"True Positives (TP):  {metrics['true_positives']}")
    print(f"False Positives (FP): {metrics['false_positives']}")
    print(f"False Negatives (FN): {metrics['false_negatives']}")
    print("-" * 65)
    print(f"Precisão (Precision): {metrics['precision']:.4f} ({metrics['precision']*100:.2f}%)")
    print(f"Revocação (Recall):   {metrics['recall']:.4f} ({metrics['recall']*100:.2f}%)")
    print(f"F1-Score:             {metrics['f1']:.4f} ({metrics['f1']*100:.2f}%)")
    print("=" * 65 + "\n")


def print_types_report(metrics: Dict[str, Any]):
    print("\n" + "=" * 65)
    print("RELATORIO OFICIAL DE AVALIACAO - TIPOS E CONCEITOS (Estacao 3)")
    print("=" * 65)
    print(f"Entidades Alinhadas:  {metrics['aligned_entities']}")
    print(f"Acurácia Global:      {metrics['accuracy']:.4f} ({metrics['accuracy']*100:.2f}%)")
    print(f"Macro F1-Score:       {metrics['macro_f1']:.4f} ({metrics['macro_f1']*100:.2f}%)")
    print(f"Micro F1-Score:       {metrics['micro_f1']:.4f} ({metrics['micro_f1']*100:.2f}%)")
    print(f"Acurácia MeSH:        {metrics['concept_link_accuracy']:.4f} ({metrics['concept_link_accuracy']*100:.2f}%)")
    print("-" * 65)
    print("Desempenho por Classe Clínica:")
    print(_format_table_row("Classe", "Precision", "Recall", "F1"))
    print("-" * 65)
    for cls_name, vals in metrics["per_class"].items():
        print(
            _format_table_row(
                cls_name[:14],
                f"{vals['precision']:.4f}",
                f"{vals['recall']:.4f}",
                f"{vals['f1']:.4f}",
            )
        )
    print("=" * 65 + "\n")


def print_relations_report(metrics: Dict[str, Any]):
    print("\n" + "=" * 65)
    print("RELATORIO OFICIAL DE AVALIACAO - RELACOES E NEGACAO (Estacao 4)")
    print("=" * 65)
    print(f"Total Predito:        {metrics['total_predicted']}")
    print(f"Total Gabarito:       {metrics['total_gold']}")
    print(f"Pares Alinhados:      {metrics['aligned_pairs']}")
    print(f"True Positives (TP):  {metrics['true_positives']}")
    print(f"False Positives (FP): {metrics['false_positives']}")
    print(f"False Negatives (FN): {metrics['false_negatives']}")
    print("-" * 65)
    print(f"Precisão de Relação:  {metrics['relation_precision']:.4f} ({metrics['relation_precision']*100:.2f}%)")
    print(f"Revocação de Relação: {metrics['relation_recall']:.4f} ({metrics['relation_recall']*100:.2f}%)")
    print(f"F1-Score de Relação:  {metrics['relation_f1']:.4f} ({metrics['relation_f1']*100:.2f}%)")
    print("-" * 65)
    print(f"Acurácia de Polaridade: {metrics['polarity_metrics']['overall_accuracy']:.4f}")
    print(f"F1 Detecção de Negação: {metrics['polarity_metrics']['negation_f1']:.4f} (Polarity=absent)")
    print(f"Acurácia de Certeza:    {metrics['certainty_metrics']['overall_accuracy']:.4f}")
    print("=" * 65 + "\n")


def print_comparison_report(comp: Dict[str, Any]):
    print("\n" + "=" * 65)
    print("CONFRONTO EXPERIMENTAL - BASELINE (P1) vs EXPERIMENTO (P2)")
    print("=" * 65)
    print(_format_table_row("Métrica", "Baseline", "Experimento", "Delta / Variação"))
    print("-" * 65)
    for m_name, vals in comp.items():
        delta_str = f"{vals['delta']:+.4f} ({vals['pct_change']:+.2f}%)"
        print(
            _format_table_row(
                m_name[:14],
                f"{vals['baseline']:.4f}",
                f"{vals['experiment']:.4f}",
                delta_str,
            )
        )
    print("=" * 65 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Script comum de avaliacao e metricas (Regra 4).")
    parser.add_argument(
        "--task",
        choices=["entities", "types", "relations", "all"],
        required=True,
        help="Tarefa a ser avaliada",
    )
    parser.add_argument("--pred", required=True, help="Caminho para o CSV de predicao")
    parser.add_argument("--gold", help="Caminho para o CSV de gabarito (default: gold_entidades.csv ou gold_relacoes.csv)")
    parser.add_argument("--baseline", help="CSV baseline (P1) para calculo comparativo de deltas")
    parser.add_argument("--match-mode", choices=["exact", "overlap"], default="exact", help="Modo de matching de entidades")
    parser.add_argument("--require-same-type", action="store_true", help="Exige que o tipo seja igual na avaliacao de entidades")
    parser.add_argument("--output-json", help="Salva o relatorio completo em formato JSON")
    args = parser.parse_args()

    pred_df = pd.read_csv(args.pred)
    gold_path = args.gold
    if not gold_path:
        if args.task in ["entities", "types"]:
            gold_path = DEFAULT_GOLD_DIR / "gold_entidades.csv"
        else:
            gold_path = DEFAULT_GOLD_DIR / "gold_relacoes.csv"

    gold_df = pd.read_csv(gold_path)
    full_report: Dict[str, Any] = {"task": args.task}

    if args.task == "entities":
        metrics = evaluate_entities(
            pred_df, gold_df, match_mode=args.match_mode, require_same_type=args.require_same_type
        )
        print_entities_report(metrics)
        full_report["metrics"] = metrics

        if args.baseline:
            base_df = pd.read_csv(args.baseline)
            base_metrics = evaluate_entities(
                base_df, gold_df, match_mode=args.match_mode, require_same_type=args.require_same_type
            )
            comp = compare_experiments(base_metrics, metrics)
            print_comparison_report(comp)
            full_report["comparison"] = comp

    elif args.task == "types":
        metrics = evaluate_types(pred_df, gold_df)
        print_types_report(metrics)
        full_report["metrics"] = metrics

        if args.baseline:
            base_df = pd.read_csv(args.baseline)
            base_metrics = evaluate_types(base_df, gold_df)
            comp = compare_experiments(base_metrics, metrics)
            print_comparison_report(comp)
            full_report["comparison"] = comp

    elif args.task == "relations":
        metrics = evaluate_relations(pred_df, gold_df)
        print_relations_report(metrics)
        full_report["metrics"] = metrics

        if args.baseline:
            base_df = pd.read_csv(args.baseline)
            base_metrics = evaluate_relations(base_df, gold_df)
            comp = compare_experiments(base_metrics, metrics)
            print_comparison_report(comp)
            full_report["comparison"] = comp

    if args.output_json:
        out_p = Path(args.output_json)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(full_report, f, indent=2, ensure_ascii=False)
        print(f"Relatório exportado para {out_p}")


if __name__ == "__main__":
    main()
