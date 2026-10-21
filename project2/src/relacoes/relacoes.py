# -*- coding: utf-8 -*-
"""Etapa 4 do Projeto 2: relacoes entre entidades clinicas.

Combina uma regra fixa para pares envolvendo o paciente com um
classificador de N-gramas para os demais pares de entidades.
"""

from __future__ import annotations

import csv
import json
import pickle
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

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

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from project2.src.avaliacao.avaliar import avaliar_relacoes  # noqa: E402
from project2.src.comum import casos_gold, ler_casos  # noqa: E402
from project2.src.relacoes.evaluation.metrics import evaluate_relations  # noqa: E402


def ler_csv(caminho: Path) -> List[Dict]:
    with open(caminho, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def escrever_csv(caminho: Path, linhas: List[Dict], colunas: List[str]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=colunas)
        w.writeheader()
        for l in linhas:
            w.writerow({c: l.get(c, "") for c in colunas})


DEFAULT_PARES_DIR = REPO_ROOT / "project2" / "data" / "silver" / "relacoes_pares"
DEFAULT_ENTIDADES = DEFAULT_PARES_DIR / "entidades.csv"
DEFAULT_GOLD_DIR = REPO_ROOT / "project2" / "data" / "gold" / "cases"
DEFAULT_TRAIN = DEFAULT_PARES_DIR / "train.csv"
DEFAULT_VAL = DEFAULT_PARES_DIR / "val.csv"
DEFAULT_TEST = DEFAULT_PARES_DIR / "test.csv"
DEFAULT_OUTPUT = REPO_ROOT / "project2" / "data" / "relacoes.csv"
DEFAULT_RESULTADOS = REPO_ROOT / "project2" / "data" / "resultados" / "relacoes.csv"
DEFAULT_RESULTADOS_MODELOS = REPO_ROOT / "project2" / "data" / "resultados" / "relacoes_modelos.csv"
DEFAULT_MODELO = REPO_ROOT / "project2" / "models" / "relacoes" / "classificador.pkl"

DEFAULT_MENCOES_TIPADAS = REPO_ROOT / "project2" / "data" / "mencoes_tipadas.csv"
DEFAULT_GOLD_MENCOES = REPO_ROOT / "project2" / "data" / "gold" / "mencoes.csv"
DEFAULT_GOLD_RELACOES = REPO_ROOT / "project2" / "data" / "gold" / "relacoes.csv"
DEFAULT_REGRAS_MENCOES = REPO_ROOT / "project2" / "data" / "regras" / "mencoes.csv"
DEFAULT_REGRAS_RELACOES = REPO_ROOT / "project2" / "data" / "regras" / "relacoes.csv"

COLUNAS_RELACOES = ["case_id", "origem", "destino", "relacao", "confianca"]
COLUNAS_RESULTADOS_RELACOES = [
    "sistema", "entrada", "criterio", "relacao",
    "precisao", "revocacao", "f1", "f1_macro", "tp", "fp", "fn",
]
NGRAM_RANGES_COMPLETO: List[Tuple[int, int]] = [(1, 1), (1, 2), (1, 3)]

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

DOMINIO_NAO_PACIENTE: Dict[str, Tuple[Set[str], Set[str]]] = {
    "HAS_RESULT": ({"Exam"}, {"ExamResult"}),
    "REVEALS": ({"Exam", "Treatment"}, {"Finding"}),
    "SUPPORTS": ({"Symptom", "Finding", "ExamResult", "History"}, {"Diagnosis"}),
    "LOCATED_IN": ({"Symptom", "Finding", "Treatment"}, {"AnatomicalSite"}),
    "TREATED_WITH": ({"Diagnosis"}, {"Treatment", "Medication"}),
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
    "linear_svm": lambda: LinearSVC(max_iter=5000, class_weight="balanced", random_state=42),
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
    esperado por project2/src/relacoes/evaluation/metrics.py:evaluate_relations.

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


def relacoes_permitidas(source_type: str, target_type: str) -> set[str]:
    """Retorna o conjunto de relacoes (nao-Patient) compativeis com (source_type, target_type)."""
    permitidas = set()
    for rel, (origens, destinos) in DOMINIO_NAO_PACIENTE.items():
        if source_type in origens and target_type in destinos:
            permitidas.add(rel)
    return permitidas


def _garantir_pares_silver() -> None:
    if not DEFAULT_TRAIN.exists() or not DEFAULT_VAL.exists() or not DEFAULT_TEST.exists():
        from project2.src.relacoes.mock.gerar import main as gerar_pares_silver
        gerar_pares_silver()


def treinar(
    train_path: Path = DEFAULT_TRAIN,
    val_path: Path = DEFAULT_VAL,
    test_path: Path = DEFAULT_TEST,
    entidades_path: Path = DEFAULT_ENTIDADES,
    modelo_path: Path = DEFAULT_MODELO,
    modelos_csv_path: Path = DEFAULT_RESULTADOS_MODELOS,
) -> Dict[Tuple[int, int], Pipeline]:
    """Treina e compara os modelos (1-1, 1-2, 1-3) nos pares silver e salva o classificador."""
    _garantir_pares_silver()
    df_entities = load_entities(entidades_path)
    df_train = prepare_features(pd.read_csv(train_path), df_entities)
    df_val = prepare_features(pd.read_csv(val_path), df_entities)
    df_test = prepare_features(pd.read_csv(test_path), df_entities)

    rows = []
    best_ngram = (1, 2)
    best_f1 = -1.0
    for model_name in NON_PATIENT_MODELS:
        for ngram_range in NGRAM_RANGES_COMPLETO:
            _, metrics = train_config(df_train, df_val, model_name, ngram_range)
            f1 = metrics["macro_f1_excluding_none"]
            rows.append({
                "model": model_name,
                "ngram_range": f"{ngram_range[0]}-{ngram_range[1]}",
                "macro_f1_excluding_none": round(f1, 4),
                "confusion_matrix": json.dumps(metrics["confusion_matrix"]),
                "per_relation": json.dumps(metrics["per_relation"]),
                "split": "val",
            })
            if model_name == "logistic_regression" and f1 > best_f1:
                best_f1 = f1
                best_ngram = ngram_range

    modelos_csv_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(modelos_csv_path, index=False)

    # Treina os pipelines finais de LogisticRegression sobre todos os pares silver nao-gold
    df_all_silver = pd.concat([df_train, df_val, df_test], ignore_index=True)
    df_non_patient = filter_non_patient_pairs(df_all_silver)
    pipelines_lr: Dict[Tuple[int, int], Pipeline] = {}
    for ngram_range in NGRAM_RANGES_COMPLETO:
        pipe = build_feature_pipeline(ngram_range, NON_PATIENT_MODELS["logistic_regression"]())
        pipe.fit(df_non_patient, df_non_patient["relation"])
        pipelines_lr[ngram_range] = pipe

    modelo_path.parent.mkdir(parents=True, exist_ok=True)
    with open(modelo_path, "wb") as f:
        pickle.dump(pipelines_lr[best_ngram], f)

    return pipelines_lr


def carregar_modelo(caminho: Path = DEFAULT_MODELO) -> Pipeline:
    if not caminho.exists():
        treinar(modelo_path=caminho)
    with open(caminho, "rb") as f:
        return pickle.load(f)


def prever_mencoes(
    mencoes: List[Dict],
    textos: Dict[str, str],
    pipeline: Optional[Pipeline] = None,
    max_dist: int = 200,
) -> List[Dict]:
    """Prediz relacoes (case_id, origem, destino, relacao, confianca) sobre mencoes tipadas."""
    if pipeline is None:
        pipeline = carregar_modelo()

    por_caso: Dict[str, List[Dict]] = {}
    for m in mencoes:
        por_caso.setdefault(m["case_id"], []).append(m)

    relacoes_saida: List[Dict] = []
    candidatos_ml: List[Dict] = []

    def _mid(m: Dict) -> str:
        return str(m.get("id") or m.get("mention_id") or m.get("ent_id") or "")

    for case_id in sorted(por_caso):
        ms = sorted(por_caso[case_id], key=lambda x: (int(x["start"]), int(x["end"])))
        texto = textos.get(case_id, "")

        # Pares candidatos entre mencoes nao-Patient dentro da janela de max_dist caracteres
        for i, m_orig in enumerate(ms):
            t_orig = m_orig.get("tipo", "")
            if not t_orig or t_orig == "Patient":
                continue
            id_orig = _mid(m_orig)
            s_orig, e_orig = int(m_orig["start"]), int(m_orig["end"])
            for j, m_dest in enumerate(ms):
                if i == j:
                    continue
                t_dest = m_dest.get("tipo", "")
                if not t_dest or t_dest == "Patient":
                    continue
                if not relacoes_permitidas(t_orig, t_dest):
                    continue
                id_dest = _mid(m_dest)
                s_dest, e_dest = int(m_dest["start"]), int(m_dest["end"])
                if s_orig == s_dest and e_orig == e_dest:
                    continue
                dist = abs(s_dest - s_orig)
                if dist > max_dist:
                    continue
                ini_entre = min(e_orig, e_dest)
                fim_entre = max(s_orig, s_dest)
                between = texto[ini_entre:fim_entre].strip() if ini_entre < fim_entre else ""
                candidatos_ml.append({
                    "case_id": case_id,
                    "source_id": id_orig,
                    "target_id": id_dest,
                    "source_type": t_orig,
                    "target_type": t_dest,
                    "between_text": between,
                    "distance_chars": dist,
                    "source_before_target": 1 if s_orig <= s_dest else 0,
                })

    relacoes_ml: List[Dict] = []
    if candidatos_ml:
        df_cand = pd.DataFrame(candidatos_ml)
        proba = pipeline.predict_proba(df_cand)
        classes = list(pipeline.named_steps["model"].classes_)
        melhores_por_alvo: Dict[Tuple[str, str, str], Tuple[ Tuple[int, float], Dict ]] = {}
        for row, p in zip(candidatos_ml, proba):
            permitidas = relacoes_permitidas(row["source_type"], row["target_type"])
            idx_max = int(p.argmax())
            rel_pred = classes[idx_max]
            conf = float(p[idx_max])
            if rel_pred == "NONE" or rel_pred not in permitidas:
                continue
            if rel_pred == "SUPPORTS" and conf < 0.75:
                continue
            item = {
                "case_id": row["case_id"],
                "origem": row["source_id"],
                "destino": row["target_id"],
                "relacao": rel_pred,
                "confianca": round(conf, 4),
            }
            if rel_pred in ("HAS_RESULT", "REVEALS", "LOCATED_IN"):
                chave_alvo = (row["case_id"], rel_pred, row["target_id"])
                # Prioriza menor distancia em caracteres e maior confianca
                score = (-int(row["distance_chars"]), conf)
                if chave_alvo not in melhores_por_alvo or score > melhores_por_alvo[chave_alvo][0]:
                    melhores_por_alvo[chave_alvo] = (score, item)
            else:
                relacoes_ml.append(item)
        relacoes_ml.extend(it for _, it in melhores_por_alvo.values())

    findings_revelados = {
        (r["case_id"], r["destino"]) for r in relacoes_ml if r["relacao"] == "REVEALS"
    }

    for case_id in sorted(por_caso):
        ms = sorted(por_caso[case_id], key=lambda x: (int(x["start"]), int(x["end"])))
        vistos_paciente = set()
        for m in ms:
            tipo = m.get("tipo", "")
            mid = _mid(m)
            rel_pac = PATIENT_RELATION_MAP.get(tipo)
            if not rel_pac or not mid:
                continue
            if rel_pac == "HAS_FINDING" and (case_id, mid) in findings_revelados:
                continue
            chave = (case_id, "P1", mid, rel_pac)
            if chave not in vistos_paciente:
                vistos_paciente.add(chave)
                relacoes_saida.append({
                    "case_id": case_id,
                    "origem": "P1",
                    "destino": mid,
                    "relacao": rel_pac,
                    "confianca": 1.0,
                })

    relacoes_saida.extend(relacoes_ml)
    return relacoes_saida


def comparar(
    mencoes_tipadas_path: Path = DEFAULT_MENCOES_TIPADAS,
    gold_mencoes_path: Path = DEFAULT_GOLD_MENCOES,
    gold_relacoes_path: Path = DEFAULT_GOLD_RELACOES,
    regras_mencoes_path: Path = DEFAULT_REGRAS_MENCOES,
    regras_relacoes_path: Path = DEFAULT_REGRAS_RELACOES,
    output_path: Path = DEFAULT_OUTPUT,
    resultados_path: Path = DEFAULT_RESULTADOS,
) -> List[Dict]:
    """Avalia regras P1 e os modelos de relacoes (isolado no gabarito e ponta-a-ponta)
    nos 8 casos gold e gera data/relacoes.csv e data/resultados/relacoes.csv."""
    pipelines_lr = treinar()
    gold_ids = set(casos_gold())
    textos = dict(ler_casos())

    gold_mencoes = [m for m in ler_csv(gold_mencoes_path) if m["case_id"] in gold_ids]
    gold_relacoes = [r for r in ler_csv(gold_relacoes_path) if r["case_id"] in gold_ids]
    regras_mencoes = [m for m in ler_csv(regras_mencoes_path) if m["case_id"] in gold_ids]
    regras_relacoes = [r for r in ler_csv(regras_relacoes_path) if r["case_id"] in gold_ids]

    todas_mencoes_tipadas = ler_csv(mencoes_tipadas_path)
    mencoes_tipadas_gold = [m for m in todas_mencoes_tipadas if m["case_id"] in gold_ids]

    linhas_res: List[Dict] = []

    def _registrar(sistema: str, entrada: str, criterio: str, res: Dict) -> None:
        tp_glob = int(res["casados"])
        fp_glob = int(res["n_pred"]) - tp_glob
        fn_glob = int(res["n_gold"]) - tp_glob
        linhas_res.append({
            "sistema": sistema,
            "entrada": entrada,
            "criterio": criterio,
            "relacao": "GLOBAL",
            "precisao": round(float(res["precisao"]), 4),
            "revocacao": round(float(res["revocacao"]), 4),
            "f1": round(float(res["f1"]), 4),
            "f1_macro": round(float(res["macro_f1"]), 4),
            "tp": tp_glob,
            "fp": fp_glob,
            "fn": fn_glob,
        })
        for rel, d in sorted(res["por_relacao"].items()):
            n_g = int(d["n"])
            tp_r = int(round(float(d["revocacao"]) * n_g))
            fn_r = n_g - tp_r
            fp_r = int(round(tp_r * (1.0 / float(d["precisao"]) - 1.0))) if float(d["precisao"]) > 0 else 0
            linhas_res.append({
                "sistema": sistema,
                "entrada": entrada,
                "criterio": criterio,
                "relacao": rel,
                "precisao": round(float(d["precisao"]), 4),
                "revocacao": round(float(d["revocacao"]), 4),
                "f1": round(float(d["f1"]), 4),
                "f1_macro": round(float(res["macro_f1"]), 4),
                "tp": tp_r,
                "fp": fp_r,
                "fn": fn_r,
            })

    # 1. Baseline Regras P1
    for crit in ("exato", "sobreposicao"):
        res_p1 = avaliar_relacoes(
            regras_relacoes, gold_relacoes, regras_mencoes, gold_mencoes, exato=(crit == "exato")
        )
        _registrar("regras P1", "regras P1", crit, res_p1)

    # 2. Modelos LR (1-1, 1-2, 1-3) em modo isolado (gabarito) e ponta a ponta (crf+tipos)
    melhor_ngram_gold = (1, 2)
    melhor_f1_gold = -1.0
    for ngram_range in NGRAM_RANGES_COMPLETO:
        label_sis = f"LR ({ngram_range[0]}-{ngram_range[1]})"
        pipe = pipelines_lr[ngram_range]

        # Modo isolado: mencoes do gabarito
        pred_iso = prever_mencoes(gold_mencoes, textos, pipeline=pipe)
        res_iso = avaliar_relacoes(
            pred_iso, gold_relacoes, gold_mencoes, gold_mencoes, exato=True
        )
        _registrar(label_sis, "gabarito", "exato", res_iso)
        if float(res_iso["f1"]) > melhor_f1_gold:
            melhor_f1_gold = float(res_iso["f1"])
            melhor_ngram_gold = ngram_range

        # Modo ponta a ponta: mencoes_tipadas.csv
        pred_e2e = prever_mencoes(mencoes_tipadas_gold, textos, pipeline=pipe)
        for crit in ("exato", "sobreposicao"):
            res_e2e = avaliar_relacoes(
                pred_e2e, gold_relacoes, mencoes_tipadas_gold, gold_mencoes, exato=(crit == "exato")
            )
            _registrar(label_sis, "crf+tipos", crit, res_e2e)

    escrever_csv(resultados_path, linhas_res, COLUNAS_RESULTADOS_RELACOES)

    # Salva o modelo vencedor e gera data/relacoes.csv para todos os 56 casos
    melhor_pipe = pipelines_lr[melhor_ngram_gold]
    with open(DEFAULT_MODELO, "wb") as f:
        pickle.dump(melhor_pipe, f)

    relacoes_todos = prever_mencoes(todas_mencoes_tipadas, textos, pipeline=melhor_pipe)
    escrever_csv(output_path, relacoes_todos, COLUNAS_RELACOES)
    return linhas_res


def generate_outputs(
    train_path: Path = DEFAULT_TRAIN,
    val_path: Path = DEFAULT_VAL,
    test_path: Path = DEFAULT_TEST,
    entidades_path: Path = DEFAULT_ENTIDADES,
    output_path: Path = DEFAULT_OUTPUT,
    resultados_path: Path = DEFAULT_RESULTADOS_MODELOS,
) -> None:
    """Mantido por compatibilidade com os testes originais da Etapa 4."""
    _garantir_pares_silver()
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
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("treinar", help="Treina o classificador de relacoes nos pares silver")
    p_prev = sub.add_parser("prever", help="Prediz relacoes em data/mencoes_tipadas.csv")
    p_prev.add_argument("--entrada", type=Path, default=DEFAULT_MENCOES_TIPADAS)
    p_prev.add_argument("--saida", type=Path, default=DEFAULT_OUTPUT)
    sub.add_parser("comparar", help="Avalia nos 8 casos gold (isolado e ponta a ponta) e gera data/relacoes.csv")

    args = parser.parse_args()
    if args.cmd == "treinar":
        treinar()
        print(f"Modelo salvo em {DEFAULT_MODELO}")
    elif args.cmd == "prever":
        textos_map = dict(ler_casos())
        mencoes_in = ler_csv(args.entrada)
        rels = prever_mencoes(mencoes_in, textos_map)
        escrever_csv(args.saida, rels, COLUNAS_RELACOES)
        print(f"{len(rels)} relacoes salvas em {args.saida}")
    else:
        linhas = comparar()
        print(f"Avaliacao concluida: {len(linhas)} linhas em {DEFAULT_RESULTADOS}")
        for l in linhas:
            if l["relacao"] == "GLOBAL":
                print(
                    f"  {l['sistema']:12s} | entrada={l['entrada']:10s} | {l['criterio']:12s} -> "
                    f"P={l['precisao']:.3f} R={l['revocacao']:.3f} F1={l['f1']:.3f} (macro={l['f1_macro']:.3f})"
                )

