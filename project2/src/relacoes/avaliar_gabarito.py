# -*- coding: utf-8 -*-
"""Avalia o pipeline treinado contra o gabarito manual dos casos reservados
(`project2/data/gold/cases/`).

Esses casos ficam de fora de `mock/gerar.py` de proposito (nao vazar no
treino), entao nao existe `entidades.csv` com os offsets de caractere das
entidades do gabarito. Este script localiza cada entidade no texto bruto
na mao (dicionario OVERRIDES abaixo) e monta os pares candidatos a partir
dai - nao generaliza sozinho para um novo caso-gabarito: ao adicionar um,
e preciso extender OVERRIDES/REGEX_KEYS/SKIP_OCCURRENCES/SEARCH_TEXT_OVERRIDE
com as entidades que o texto desse novo caso nao deixa achar literalmente
pelo label salvo em `<case_id>-nodes.csv`.
"""

from __future__ import annotations

import csv
import re
from itertools import combinations
from typing import Dict, List

import pandas as pd

from project2.src.relacoes.relacoes import (
    DEFAULT_ENTIDADES,
    DEFAULT_GOLD_DIR,
    DEFAULT_TRAIN,
    DEFAULT_VAL,
    evaluate_against_gold,
    load_entities,
    predict_relations,
    prepare_features,
    select_best_lr_config,
)

CASOS = ["PMC4630775_01", "PMC6083636_03"]

# snippet usado para localizar cada entidade no texto quando o label salvo
# em <case_id>-nodes.csv nao aparece literalmente (ex.: "right eye" no
# label, "RE" no texto) ou quando ha mais de uma ocorrencia e a certa nao
# e a primeira.
OVERRIDES = {
    ("PMC4630775_01", "A3"): "dorsal hand",
    ("PMC6083636_03", "A1"): r"\bRE\b",
    ("PMC6083636_03", "A2"): r"\bLE\b",
    ("PMC6083636_03", "R3"): "14 out of 15",
    ("PMC6083636_03", "R4"): "15 out of 15",
    ("PMC6083636_03", "R5"): "127",
    ("PMC6083636_03", "R6"): "106",
    ("PMC6083636_03", "F1"): "horizontal nystagmus",
}
REGEX_KEYS = {("PMC6083636_03", "A1"), ("PMC6083636_03", "A2")}
SKIP_OCCURRENCES = {("PMC6083636_03", "F2"): 1}
SEARCH_TEXT_OVERRIDE = {("PMC6083636_03", "F2"): "nystagmus"}


def _carregar_nodes(case_id: str) -> List[Dict]:
    path = DEFAULT_GOLD_DIR / case_id / f"{case_id}-nodes.csv"
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _carregar_texto(case_id: str) -> str:
    path = DEFAULT_GOLD_DIR / case_id / f"{case_id}-texto.txt"
    return path.read_text(encoding="utf-8")


def localizar_entidades(case_id: str, texto: str) -> Dict[str, Dict]:
    """IDs do gabarito -> {type, start, end} no texto bruto do caso."""
    resultado: Dict[str, Dict] = {}
    for node in _carregar_nodes(case_id):
        node_id = node["node_id"]
        key = (case_id, node_id)
        if node["type"] == "Patient":
            resultado[node_id] = {"type": "Patient", "start": 0, "end": 0}
            continue
        snippet = OVERRIDES.get(key, SEARCH_TEXT_OVERRIDE.get(key, node["label"]))
        skip = SKIP_OCCURRENCES.get(key, 0)
        if key in REGEX_KEYS:
            m = list(re.finditer(snippet, texto))[skip]
            pos, fim = m.start(), m.end()
        else:
            texto_lower, snippet_lower = texto.lower(), snippet.lower()
            pos, start_search = -1, 0
            for _ in range(skip + 1):
                pos = texto_lower.find(snippet_lower, start_search)
                start_search = pos + 1
            fim = pos + len(snippet)
        resultado[node_id] = {"type": node["type"], "start": pos, "end": fim}
    return resultado


def _carregar_gold(case_id: str) -> pd.DataFrame:
    path = DEFAULT_GOLD_DIR / case_id / f"{case_id}-relations.csv"
    return pd.read_csv(path)


def _between(texto: str, e1: Dict, e2: Dict) -> str:
    inicio, fim = min(e1["end"], e2["end"]), max(e1["start"], e2["start"])
    return texto[inicio:fim].strip() if inicio < fim else ""


def montar_candidatos(case_id: str, texto: str, entidades: Dict[str, Dict], gold: pd.DataFrame) -> List[Dict]:
    """Um candidato por par de entidades do caso: direcao do gabarito para
    os pares que estao nele, direcao 'quem aparece primeiro no texto' para
    o resto (mesma convencao de mock/gerar.py:gerar_pares_do_caso)."""
    pares_gold = {(r.source, r.target) for r in gold.itertuples()}
    linhas = []
    for a, b in combinations(entidades.keys(), 2):
        if (a, b) in pares_gold:
            source_id, target_id = a, b
        elif (b, a) in pares_gold:
            source_id, target_id = b, a
        else:
            ea, eb = entidades[a], entidades[b]
            source_id, target_id = (a, b) if ea["start"] <= eb["start"] else (b, a)
        es, et = entidades[source_id], entidades[target_id]
        linhas.append({
            "case_id": case_id,
            "source_id": source_id,
            "target_id": target_id,
            "source_type": es["type"],
            "target_type": et["type"],
            "between_text": _between(texto, es, et),
            "distance_chars": abs(et["start"] - es["start"]),
            "polarity": "present",
            "certainty": "asserted",
        })
    return linhas


def avaliar() -> Dict:
    todas_linhas: List[Dict] = []
    entidades_rows: List[Dict] = []
    for case_id in CASOS:
        texto = _carregar_texto(case_id)
        entidades = localizar_entidades(case_id, texto)
        gold = _carregar_gold(case_id)
        todas_linhas.extend(montar_candidatos(case_id, texto, entidades, gold))
        for ent_id, info in entidades.items():
            entidades_rows.append({"case_id": case_id, "ent_id": ent_id, "char_start": info["start"]})

    df_candidatos = prepare_features(pd.DataFrame(todas_linhas), pd.DataFrame(entidades_rows))

    df_entidades_treino = load_entities(DEFAULT_ENTIDADES)
    df_train = prepare_features(pd.read_csv(DEFAULT_TRAIN), df_entidades_treino)
    df_val = prepare_features(pd.read_csv(DEFAULT_VAL), df_entidades_treino)
    _, pipeline, _ = select_best_lr_config(df_train, df_val)

    df_pred = predict_relations(df_candidatos, pipeline)
    return evaluate_against_gold(df_pred, CASOS, gold_dir=DEFAULT_GOLD_DIR), df_pred


if __name__ == "__main__":
    resultado, df_pred = avaliar()
    print(f"Candidatos avaliados: {len(df_pred)} predicoes (relation != NONE)")
    print(df_pred[["case_id", "source", "target", "relation", "confidence"]].to_string(index=False))
    print("\n=== Avaliacao contra o gabarito manual ===")
    print(f"total_predicted={resultado['total_predicted']}  total_gold={resultado['total_gold']}  "
          f"aligned_pairs={resultado['aligned_pairs']}")
    print(f"relation_precision={resultado['relation_precision']:.3f}  "
          f"relation_recall={resultado['relation_recall']:.3f}  "
          f"relation_f1={resultado['relation_f1']:.3f}")
    print("per_relation:")
    for rel, m in resultado["per_relation"].items():
        print(f"  {rel:16} precision={m['precision']:.2f} recall={m['recall']:.2f} "
              f"f1={m['f1']:.2f} support={m['support']}")
