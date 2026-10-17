# -*- coding: utf-8 -*-
"""Gerenciamento e geracao dos splits deterministicos de casos clinicos.

Garante a divisao estrita por case_id entre treino, validacao e teste,
assegurando que nao haja vazamento de dados (data leakage) entre os conjuntos.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, List, Sequence
import numpy as np
import pandas as pd

DEFAULT_INPUT = Path("project1/data/case_texts.csv")
DEFAULT_OUTPUT = Path("project2/data/splits.json")


def create_case_splits(
    case_ids: Sequence[str],
    train_count: int = 40,
    val_count: int = 8,
    test_count: int = 8,
    random_state: int = 42,
) -> Dict[str, any]:
    """Divide deterministicamente a lista de case_ids em train, val e test.

    Args:
        case_ids: Sequencia de identificadores unicos de caso.
        train_count: Quantidade de casos para o conjunto de treino.
        val_count: Quantidade de casos para o conjunto de validacao.
        test_count: Quantidade de casos para o conjunto de teste.
        random_state: Semente do gerador pseudo-aleatorio para reprodutibilidade.

    Returns:
        Dicionario contendo 'metadata', 'train', 'val' e 'test'.
    """
    unique_ids = sorted(list(set(case_ids)))
    total = len(unique_ids)
    target_total = train_count + val_count + test_count

    if total != target_total:
        raise ValueError(
            f"O total de casos ({total}) difere da soma solicitada "
            f"({train_count} + {val_count} + {test_count} = {target_total})."
        )

    rng = np.random.RandomState(random_state)
    shuffled = list(unique_ids)
    rng.shuffle(shuffled)

    train_ids = sorted(shuffled[:train_count])
    val_ids = sorted(shuffled[train_count : train_count + val_count])
    test_ids = sorted(shuffled[train_count + val_count :])

    # Validacoes de integridade e isolamento
    train_set = set(train_ids)
    val_set = set(val_ids)
    test_set = set(test_ids)

    assert len(train_set & val_set) == 0, "Vazamento detectado entre train e val!"
    assert len(train_set & test_set) == 0, "Vazamento detectado entre train e test!"
    assert len(val_set & test_set) == 0, "Vazamento detectado entre val e test!"
    assert train_set | val_set | test_set == set(unique_ids), "Conjunto de casos incompleto!"

    return {
        "metadata": {
            "random_state": random_state,
            "total_cases": total,
            "train_count": len(train_ids),
            "val_count": len(val_ids),
            "test_count": len(test_ids),
        },
        "train": train_ids,
        "val": val_ids,
        "test": test_ids,
    }


def save_splits(splits: Dict[str, any], output_path: str | Path) -> Path:
    """Salva a estrutura de splits em arquivo JSON."""
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(splits, f, indent=2, ensure_ascii=False)
    return out_file


def load_splits(splits_path: str | Path) -> Dict[str, any]:
    """Carrega os splits existentes de um arquivo JSON."""
    with open(splits_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Gera splits deterministicos por case_id.")
    parser.add_argument("--input", type=str, default=str(DEFAULT_INPUT), help="Caminho para case_texts.csv")
    parser.add_argument("--output", type=str, default=str(DEFAULT_OUTPUT), help="Caminho de saida do splits.json")
    parser.add_argument("--train", type=int, default=40, help="Quantidade de casos de treino")
    parser.add_argument("--val", type=int, default=8, help="Quantidade de casos de validacao")
    parser.add_argument("--test", type=int, default=8, help="Quantidade de casos de teste")
    parser.add_argument("--seed", type=int, default=42, help="Semente pseudo-aleatoria")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Arquivo de entrada nao encontrado: {input_path}")

    df = pd.read_csv(input_path)
    if "case_id" not in df.columns:
        raise KeyError("Coluna 'case_id' obrigatoria em case_texts.csv")

    case_ids = df["case_id"].dropna().unique().tolist()
    splits = create_case_splits(
        case_ids=case_ids,
        train_count=args.train,
        val_count=args.val,
        test_count=args.test,
        random_state=args.seed,
    )

    out_file = save_splits(splits, args.output)
    print(f"Splits gerados com sucesso em {out_file}:")
    print(f"  Treino: {splits['metadata']['train_count']} casos")
    print(f"  Validacao: {splits['metadata']['val_count']} casos")
    print(f"  Teste: {splits['metadata']['test_count']} casos")


if __name__ == "__main__":
    main()
