# -*- coding: utf-8 -*-
"""Avalia o pipeline treinado contra o gabarito manual dos casos reservados
(`project2/data/gold/cases/`, esquema oficial consolidado por
`project2/src/montagem/data/gold_manager.py`).

Le `<case_id>-entities.csv` (ent_id, char_start, char_end, type ja prontos,
gerados pelo starter pack oficial) e monta os pares candidatos a partir dai -
nao precisa mais localizar entidades no texto na mao, porque o esquema
oficial ja traz offset de caractere para cada candidato (inclusive os que
nos mesmos adicionamos para os resultados de exame nao capturados pelo
chunker automatico, ver `<case_id>-entities.csv`).

A coluna `type` do `entities.csv` oficial herda o mesmo bug de casamento de
texto do `weak_supervision.py` (ver project2/docs/relacoes.md): sitios
anatomicos mencionados dentro do blob de sintoma do Projeto 1 (ex. "palm",
"skin", "thumb") saem rotulados `Symptom` em vez de `AnatomicalSite`, e
"RE"/"LE" saem sem tipo (ou `Exam`, errado). Corrigir isso no proprio
`entities.csv` esta fora de escopo (arquivo compartilhado, usado por todas
as 8 anotacoes-ouro do time, nao so as nossas) - por isso `TYPE_OVERRIDE`
reaplica, so para os ent_id dos nossos 2 casos, os tipos que ja haviamos
determinado lendo o texto na v1 deste gabarito. `PATIENT_ENT_ID` cobre o
unico dado que o oficial nao marca nenhuma versao (`type` vazio para o
`Patient`, porque "patient" nao casa contra o label do no do Projeto 1).
"""

from __future__ import annotations

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

PATIENT_ENT_ID = {
    "PMC4630775_01": "t8",
    "PMC6083636_03": "t9",
}

TYPE_OVERRIDE = {
    ("PMC4630775_01", "t10"): "AnatomicalSite",  # palm
    ("PMC4630775_01", "t12"): "AnatomicalSite",  # skin
    ("PMC4630775_01", "t13"): "AnatomicalSite",  # right dorsal hand
    ("PMC4630775_01", "t14"): "AnatomicalSite",  # circumferential forearm
    ("PMC4630775_01", "t16"): "AnatomicalSite",  # thumb
    ("PMC6083636_03", "t1"): "Exam",             # best corrected visual acuity
    ("PMC6083636_03", "t2"): "ExamResult",       # 0.50 logMAR
    ("PMC6083636_03", "t3"): "AnatomicalSite",   # RE
    ("PMC6083636_03", "t4"): "ExamResult",       # 0.40 logMAR
    ("PMC6083636_03", "t5"): "AnatomicalSite",   # LE
    ("PMC6083636_03", "t7"): "Exam",             # Ishihara isochromatic plates
    ("PMC6083636_03", "t11"): "AnatomicalSite",  # RE
    ("PMC6083636_03", "t12"): "AnatomicalSite",  # LE
    ("PMC6083636_03", "t13"): "Exam",            # Farnsworth Munsell 100-Hue
    ("PMC6083636_03", "t15"): "AnatomicalSite",  # RE
    ("PMC6083636_03", "t16"): "AnatomicalSite",  # LE
    ("PMC6083636_03", "t21"): "ExamResult",      # intermittent exotropia
    ("PMC6083636_03", "t23"): "Finding",         # horizontal nystagmus
    ("PMC6083636_03", "t28"): "Finding",         # nystagmus (primary gaze)
}


def _carregar_texto(case_id: str) -> str:
    path = DEFAULT_GOLD_DIR / case_id / "case_text.txt"
    return path.read_text(encoding="utf-8")


def _carregar_entidades(case_id: str) -> Dict[str, Dict]:
    """Candidatos tipados do caso (Patient + TYPE_OVERRIDE + tipo original do
    CSV quando nao vazio). Descarta candidatos sem tipo - `entities.csv`
    oficial inclui todo chunk do pos_bio (inclusive ruido como "Figure",
    "quality", frases das perguntas no fim do texto), mas o treino real
    (`mencoes.csv` da Etapa 2) so contem mencoes ja tipadas; manter o ruido
    aqui testaria o modelo fora da distribuicao em que foi treinado."""
    path = DEFAULT_GOLD_DIR / case_id / f"{case_id}-entities.csv"
    df = pd.read_csv(path)
    patient_id = PATIENT_ENT_ID[case_id]
    entidades: Dict[str, Dict] = {}
    for row in df.itertuples():
        if row.ent_id == patient_id:
            tipo = "Patient"
        else:
            tipo = TYPE_OVERRIDE.get(
                (case_id, row.ent_id), str(row.type) if pd.notna(row.type) else ""
            )
        if not tipo:
            continue
        entidades[row.ent_id] = {"type": tipo, "start": int(row.char_start), "end": int(row.char_end)}
    return entidades


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
        entidades = _carregar_entidades(case_id)
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
