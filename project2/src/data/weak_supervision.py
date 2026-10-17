# -*- coding: utf-8 -*-
"""Gerador de dados de supervisao fraca (Weak Supervision) e Silver Standard.

Utiliza as saidas consolidadas e regras do Projeto 1 para rotular automaticamente
o corpus clinico (56 casos), gerando datasets de treinamento, validacao e teste
para todas as estacoes do Projeto 2:
  - Estacao 2 (Caio): Datasets CoNLL (boundary e typed) e entidades.csv.
  - Estacao 3 (Lucas): entidades_tipadas.csv e dataset de treino para classificacao.
  - Estacao 4 (Joao): relacoes.csv e dataset de treino para pares com negativos.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

# Garante acesso aos modulos do projeto 1
REPO_ROOT = Path(__file__).resolve().parents[3]
SINTAGMAS_DIR = REPO_ROOT / "project1" / "src" / "sintagmas"
if str(SINTAGMAS_DIR) not in sys.path:
    sys.path.insert(0, str(SINTAGMAS_DIR))

try:
    import pos_bio
except ImportError:
    pos_bio = None

DEFAULT_CASE_TEXTS = REPO_ROOT / "project1" / "data" / "case_texts.csv"
DEFAULT_PROCESSED_DIR = REPO_ROOT / "project1" / "data" / "processed"
DEFAULT_SPLITS_PATH = REPO_ROOT / "project2" / "data" / "splits.json"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "project2" / "data" / "silver"

DETERMINERS = {"a", "an", "the", "this", "that", "these", "those"}


def parse_attributes(raw_attrs: Any) -> Dict[str, str]:
    """Converte a string de atributos 'k1=v1; k2=v2' em um dicionario."""
    if not isinstance(raw_attrs, str) or not raw_attrs.strip():
        return {}
    res = {}
    for part in raw_attrs.split("; "):
        if "=" in part:
            k, v = part.split("=", 1)
            res[k.strip()] = v.strip()
    return res


def clean_entity_text_and_offsets(
    tokens: List[Any],
    case_text: str,
) -> Tuple[int, int, str]:
    """Remove determinantes iniciais do sintagma preservando offsets exatos."""
    start_tok_idx = 0
    while (
        start_tok_idx < len(tokens) - 1
        and tokens[start_tok_idx].text.lower() in DETERMINERS
    ):
        start_tok_idx += 1

    char_start = tokens[start_tok_idx].start
    char_end = tokens[-1].end
    texto = case_text[char_start:char_end]
    return char_start, char_end, texto


class WeakSupervisionGenerator:
    """Extrai e compila anotacoes fracas a partir das regras do Projeto 1."""

    def __init__(
        self,
        case_texts_path: Path = DEFAULT_CASE_TEXTS,
        processed_dir: Path = DEFAULT_PROCESSED_DIR,
        splits_path: Path = DEFAULT_SPLITS_PATH,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
    ):
        if pos_bio is None:
            raise ImportError("Nao foi possivel importar pos_bio de project1/src/sintagmas")

        self.case_texts_path = Path(case_texts_path)
        self.processed_dir = Path(processed_dir)
        self.splits_path = Path(splits_path)
        self.output_dir = Path(output_dir)
        self.tagger = pos_bio.HMMTagger()

    def load_case_nodes_and_edges(
        self, case_id: str
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Carrega os nodes e edges gerados pelo Projeto 1 para o caso."""
        nodes_file = self.processed_dir / f"{case_id}-nodes.csv"
        edges_file = self.processed_dir / f"{case_id}-edges.csv"

        df_nodes = pd.read_csv(nodes_file) if nodes_file.exists() else pd.DataFrame()
        df_edges = pd.read_csv(edges_file) if edges_file.exists() else pd.DataFrame()
        return df_nodes, df_edges

    def extract_case_data(
        self, case_id: str, case_text: str
    ) -> Dict[str, Any]:
        """Processa um caso clinico individual e extrai entidades, tipos e relacoes."""
        tokens, chunks, spans, _ = pos_bio.process(case_text, self.tagger)
        df_nodes, df_edges = self.load_case_nodes_and_edges(case_id)

        # 1. Mapa de nós clínicos e conceitos do P1
        concept_map: Dict[str, str] = {}
        node_type_map: Dict[str, str] = {}
        node_label_map: Dict[str, str] = {}
        node_polarity_map: Dict[str, str] = {}

        if not df_nodes.empty:
            for _, row in df_nodes.iterrows():
                nid = str(row["node_id"])
                ntype = str(row["type"])
                label = str(row["label"])
                attrs = parse_attributes(row.get("attributes", ""))

                node_type_map[nid] = ntype
                node_label_map[nid] = label
                if "polarity" in attrs:
                    node_polarity_map[nid] = attrs["polarity"]

                if ntype == "Concept" and "code" in attrs:
                    concept_map[nid] = attrs["code"]

        # Mapa de arestas SAME_AS para resolver códigos MeSH de entidades
        entity_concept_code: Dict[str, str] = {}
        clinical_edges: List[Dict[str, Any]] = []

        if not df_edges.empty:
            for _, row in df_edges.iterrows():
                src = str(row["source_id"])
                tgt = str(row["target_id"])
                rel = str(row["relation"])
                attrs = parse_attributes(row.get("attributes", ""))

                if rel == "SAME_AS" and tgt in concept_map:
                    entity_concept_code[src] = concept_map[tgt]
                elif rel != "SAME_AS":
                    clinical_edges.append(
                        {
                            "source_id": src,
                            "target_id": tgt,
                            "relation": rel,
                            "attributes": attrs,
                        }
                    )

        # 2. Extrai entidades a partir dos sintagmas do pos_bio
        entities: List[Dict[str, Any]] = []
        ent_by_id: Dict[str, Dict[str, Any]] = {}

        for idx, ch in enumerate(chunks):
            char_start, char_end, texto = clean_entity_text_and_offsets(ch, case_text)
            ent_id = f"t{idx + 1}"

            # Tenta casar tipo e conceito com base no pos_bio spans ou nos nodes do P1
            ent_type = ""
            concept_code = ""
            polarity = "present"
            matched_node_id = None

            # Procura casamento direto com os nós do P1
            texto_lower = texto.lower()
            for nid, label in node_label_map.items():
                if node_type_map[nid] == "Concept":
                    continue
                label_lower = label.lower()
                if texto_lower == label_lower or label_lower in texto_lower or texto_lower in label_lower:
                    ent_type = node_type_map[nid]
                    concept_code = entity_concept_code.get(nid, "")
                    polarity = node_polarity_map.get(nid, "present")
                    matched_node_id = nid
                    break

            # Se ainda nao tem tipo, consulta spans do pos_bio (gazetteers e sintaxe)
            if not ent_type:
                ch_tok_indices = {t.index for t in ch}
                for sp in spans:
                    sp_tok_indices = {t.index for t in sp.tokens}
                    if ch_tok_indices & sp_tok_indices:
                        ent_type = sp.type
                        break

            # Identificacao de negação no contexto imediato
            prec_window = case_text[max(0, char_start - 35) : char_start].lower()
            if re.search(r"\b(no|without|denies|denied|negative for|free of|no evidence of)\b", prec_window):
                polarity = "absent"

            ent_record = {
                "case_id": case_id,
                "ent_id": ent_id,
                "char_start": char_start,
                "char_end": char_end,
                "texto": texto,
                "type": ent_type,
                "concept_code": concept_code,
                "polarity": polarity,
                "matched_node_id": matched_node_id,
                "confianca": 1.0 if ent_type else 0.0,
            }
            entities.append(ent_record)
            ent_by_id[ent_id] = ent_record

        # 3. Geração de linhas CoNLL (boundary e typed)
        conll_sentences: List[List[Tuple[str, str, str, str]]] = []
        current_sentence: List[Tuple[str, str, str, str]] = []

        # Mapa de char offset para tags BIO
        token_bio_boundary: Dict[int, str] = {}
        token_bio_typed: Dict[int, str] = {}

        for ent in entities:
            e_start = ent["char_start"]
            e_end = ent["char_end"]
            etype = ent["type"] or "ENT"

            # Encontra tokens dentro deste span
            matching_tokens = [t for t in tokens if t.start >= e_start and t.end <= e_end]
            for i, t in enumerate(matching_tokens):
                prefix = "B-" if i == 0 else "I-"
                token_bio_boundary[t.index] = f"{prefix}ENT"
                token_bio_typed[t.index] = f"{prefix}{etype}"

        for tok in tokens:
            bio_b = token_bio_boundary.get(tok.index, "O")
            bio_t = token_bio_typed.get(tok.index, "O")
            current_sentence.append((tok.text, tok.tag or "NOUN", bio_b, bio_t))

            # Fim de sentença em pontuação terminadora
            if tok.text in {".", "!", "?"}:
                conll_sentences.append(current_sentence)
                current_sentence = []

        if current_sentence:
            conll_sentences.append(current_sentence)

        # 4. Geração de Relações clínicas
        relations: List[Dict[str, Any]] = []
        relation_train_samples: List[Dict[str, Any]] = []
        positive_pairs: Set[Tuple[str, str]] = set()

        # Mapeia arestas clínicas do P1 para entidades extraídas
        for edge in clinical_edges:
            src_nid = edge["source_id"]
            tgt_nid = edge["target_id"]
            rel_name = edge["relation"]
            edge_attrs = edge["attributes"]
            certainty = edge_attrs.get("certainty", "asserted")

            # Localiza ent_ids que casaram com estes nós
            src_ents = [e for e in entities if e["matched_node_id"] == src_nid]
            tgt_ents = [e for e in entities if e["matched_node_id"] == tgt_nid]

            for s_ent in src_ents:
                for t_ent in tgt_ents:
                    s_id = s_ent["ent_id"]
                    t_id = t_ent["ent_id"]
                    if s_id == t_id or (s_id, t_id) in positive_pairs:
                        continue

                    pol = t_ent["polarity"]
                    relations.append(
                        {
                            "case_id": case_id,
                            "source": s_id,
                            "target": t_id,
                            "relation": rel_name,
                            "polarity": pol,
                            "certainty": certainty,
                            "confianca": 1.0,
                        }
                    )
                    positive_pairs.add((s_id, t_id))

                    # Contexto intervening para treinamento do classificador
                    c_start = min(s_ent["char_end"], t_ent["char_end"])
                    c_end = max(s_ent["char_start"], t_ent["char_start"])
                    between_text = case_text[c_start:c_end].strip() if c_start < c_end else ""

                    relation_train_samples.append(
                        {
                            "case_id": case_id,
                            "source_id": s_id,
                            "target_id": t_id,
                            "source_text": s_ent["texto"],
                            "target_text": t_ent["texto"],
                            "source_type": s_ent["type"],
                            "target_type": t_ent["type"],
                            "between_text": between_text,
                            "distance_chars": abs(t_ent["char_start"] - s_ent["char_start"]),
                            "relation": rel_name,
                            "polarity": pol,
                            "certainty": certainty,
                            "is_positive": 1,
                        }
                    )

        # 5. Amostragem de pares negativos (relation = NONE)
        # Seleciona pares de entidades proximas sem relacao para treino do classificador
        neg_count = 0
        max_negatives = max(len(relation_train_samples) * 2, 10)

        for i, e1 in enumerate(entities):
            for e2 in entities[i + 1 :]:
                p1 = (e1["ent_id"], e2["ent_id"])
                p2 = (e2["ent_id"], e1["ent_id"])

                if p1 in positive_pairs or p2 in positive_pairs:
                    continue

                dist = abs(e2["char_start"] - e1["char_start"])
                # Apenas pares na mesma vizinhança contextual (< 200 caracteres)
                if dist <= 200:
                    c_start = min(e1["char_end"], e2["char_end"])
                    c_end = max(e1["char_start"], e2["char_start"])
                    between_text = case_text[c_start:c_end].strip() if c_start < c_end else ""

                    relation_train_samples.append(
                        {
                            "case_id": case_id,
                            "source_id": e1["ent_id"],
                            "target_id": e2["ent_id"],
                            "source_text": e1["texto"],
                            "target_text": e2["texto"],
                            "source_type": e1["type"],
                            "target_type": e2["type"],
                            "between_text": between_text,
                            "distance_chars": dist,
                            "relation": "NONE",
                            "polarity": "present",
                            "certainty": "asserted",
                            "is_positive": 0,
                        }
                    )
                    neg_count += 1
                    if neg_count >= max_negatives:
                        break
            if neg_count >= max_negatives:
                break

        return {
            "entities": entities,
            "conll_sentences": conll_sentences,
            "relations": relations,
            "relation_train_samples": relation_train_samples,
        }

    def generate_all(self) -> Dict[str, Any]:
        """Gera todos os arquivos do Silver Standard organizados por split."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Carrega splits e textos
        splits = json.loads(self.splits_path.read_text(encoding="utf-8"))
        df_texts = pd.read_csv(self.case_texts_path)
        case_texts = dict(zip(df_texts["case_id"], df_texts["case_text"]))

        split_results: Dict[str, Dict[str, List[Any]]] = {
            "train": {"entities": [], "conll": [], "relations": [], "rel_train": []},
            "val": {"entities": [], "conll": [], "relations": [], "rel_train": []},
            "test": {"entities": [], "conll": [], "relations": [], "rel_train": []},
        }

        all_entities = []
        all_relations = []

        print(f"Iniciando geracao de supervisao fraca para {len(case_texts)} casos...")

        for case_id, text in case_texts.items():
            # Determina a qual split o caso pertence
            target_split = "train"
            for s_name in ["train", "val", "test"]:
                if case_id in splits.get(s_name, []):
                    target_split = s_name
                    break

            case_data = self.extract_case_data(case_id, text)

            split_results[target_split]["entities"].extend(case_data["entities"])
            split_results[target_split]["conll"].extend(case_data["conll_sentences"])
            split_results[target_split]["relations"].extend(case_data["relations"])
            split_results[target_split]["rel_train"].extend(case_data["relation_train_samples"])

            all_entities.extend(case_data["entities"])
            all_relations.extend(case_data["relations"])

        # Gravacao dos arquivos por split
        for s_name in ["train", "val", "test"]:
            data = split_results[s_name]

            # 1. entidades.csv (Estacao 2 - Caio)
            df_ent = pd.DataFrame(data["entities"])
            if not df_ent.empty:
                # entidades.csv puro
                df_ent[["case_id", "ent_id", "char_start", "char_end", "texto"]].to_csv(
                    self.output_dir / f"silver_entidades_{s_name}.csv", index=False
                )
                # entidades_tipadas.csv (Estacao 3 - Lucas)
                df_ent[
                    [
                        "case_id",
                        "ent_id",
                        "char_start",
                        "char_end",
                        "texto",
                        "type",
                        "concept_code",
                        "confianca",
                    ]
                ].to_csv(self.output_dir / f"silver_entidades_tipadas_{s_name}.csv", index=False)

            # 2. CoNLL (Estacao 2 - Caio CRF)
            conll_path = self.output_dir / f"ner_{s_name}.conll"
            with open(conll_path, "w", encoding="utf-8") as f:
                for sent in data["conll"]:
                    for tok, tag, bio_b, bio_t in sent:
                        f.write(f"{tok}\t{tag}\t{bio_b}\t{bio_t}\n")
                    f.write("\n")

            # 3. relacoes.csv (Estacao 4 - Joao)
            df_rel = pd.DataFrame(data["relations"])
            if not df_rel.empty:
                df_rel[
                    [
                        "case_id",
                        "source",
                        "target",
                        "relation",
                        "polarity",
                        "certainty",
                        "confianca",
                    ]
                ].to_csv(self.output_dir / f"silver_relacoes_{s_name}.csv", index=False)

            # 4. Dataset enriquecido para treino de relacoes
            df_rel_train = pd.DataFrame(data["rel_train"])
            if not df_rel_train.empty:
                df_rel_train.to_csv(
                    self.output_dir / f"relations_training_{s_name}.csv", index=False
                )

        # Arquivos consolidados globais (mocks imediatos para toda a equipe)
        df_all_ent = pd.DataFrame(all_entities)
        if not df_all_ent.empty:
            df_all_ent[["case_id", "ent_id", "char_start", "char_end", "texto"]].to_csv(
                self.output_dir / "entidades.csv", index=False
            )
            df_all_ent[
                [
                    "case_id",
                    "ent_id",
                    "char_start",
                    "char_end",
                    "texto",
                    "type",
                    "concept_code",
                    "confianca",
                ]
            ].to_csv(self.output_dir / "entidades_tipadas.csv", index=False)

        df_all_rel = pd.DataFrame(all_relations)
        if not df_all_rel.empty:
            df_all_rel[
                [
                    "case_id",
                    "source",
                    "target",
                    "relation",
                    "polarity",
                    "certainty",
                    "confianca",
                ]
            ].to_csv(self.output_dir / "relacoes.csv", index=False)

        summary = {
            "total_entities": len(all_entities),
            "total_relations": len(all_relations),
            "train_entities": len(split_results["train"]["entities"]),
            "val_entities": len(split_results["val"]["entities"]),
            "test_entities": len(split_results["test"]["entities"]),
            "train_relations": len(split_results["train"]["relations"]),
            "val_relations": len(split_results["val"]["relations"]),
            "test_relations": len(split_results["test"]["relations"]),
            "output_dir": str(self.output_dir),
        }

        # Salva manifesto de resumo
        with open(self.output_dir / "summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        return summary


def main():
    parser = argparse.ArgumentParser(description="Gera dados Silver via supervisao fraca.")
    parser.add_argument("--texts", default=str(DEFAULT_CASE_TEXTS), help="Caminho para case_texts.csv")
    parser.add_argument("--processed", default=str(DEFAULT_PROCESSED_DIR), help="Caminho para pasta processed")
    parser.add_argument("--splits", default=str(DEFAULT_SPLITS_PATH), help="Caminho para splits.json")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_DIR), help="Diretorio de saida do silver")
    args = parser.parse_args()

    gen = WeakSupervisionGenerator(
        case_texts_path=Path(args.texts),
        processed_dir=Path(args.processed),
        splits_path=Path(args.splits),
        output_dir=Path(args.output),
    )
    summary = gen.generate_all()
    print("Supervisao fraca concluida com sucesso!")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
