# -*- coding: utf-8 -*-
# LEGADO: primeira rota de montagem/avaliação da #29, substituída por
# src/montagem/montagem.py, src/dados/ e src/avaliacao/. Fora do pipeline final.
"""Montador de Grafos de Conhecimento Clinico (nodes.csv e edges.csv).

Integra as predicoes das estacoes a montante (Lucas e Joao) ou os mocks do P1:
  1. Aplica o agrupador hierarquico para deduplicar mencoes repetidas ("um no por coisa").
  2. Mapeia mencoes para identificadores clinicos tipados (P1, S1, E1, F1, A1, D1, M1...).
  3. Cria nos Concept e arestas SAME_AS para termos vinculados ao MeSH.
  4. Mapeia arestas clinicas, eliminando auto-loops e arestas redundantes.
  5. Serializa no formato canonico do Projeto 1.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

from project2.src.montagem.assembly.clustering import (
    HierarchicalMentionClusterer,
    extract_attributes_from_mention,
)

TYPE_PREFIXES = {
    "Patient": "P",
    "Symptom": "S",
    "Exam": "E",
    "Finding": "F",
    "AnatomicalSite": "A",
    "Diagnosis": "D",
    "Medication": "M",
    "Treatment": "T",
    "Outcome": "O",
    "ExamResult": "R",
    "Concept": "C",
}


def _format_attributes_str(attrs: Dict[str, Any]) -> str:
    """Serializa dicionario de atributos no formato 'k1=v1; k2=v2'."""
    parts = []
    for k, v in attrs.items():
        if v is not None and str(v).strip():
            parts.append(f"{k}={str(v).strip()}")
    return "; ".join(parts)


class CaseGraphBuilder:
    """Constroi o grafo de conhecimento clinico para um caso individual."""

    def __init__(self, clusterer: Optional[HierarchicalMentionClusterer] = None):
        self.clusterer = clusterer or HierarchicalMentionClusterer()

    def build_case_graph(
        self,
        case_id: str,
        df_entities: pd.DataFrame,
        df_relations: pd.DataFrame,
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Processa entidades e relacoes de um caso e retorna (nodes_df, edges_df)."""
        # Filtra entidades do caso
        case_ents = df_entities[df_entities["case_id"] == case_id].copy()
        case_rels = df_relations[df_relations["case_id"] == case_id].copy()

        # 1. Filtra apenas entidades tipadas
        typed_ents = case_ents[
            case_ents["type"].notna()
            & (case_ents["type"].astype(str).str.strip() != "")
            & (case_ents["type"].astype(str).str.strip().str.upper() != "UNKNOWN")
        ]

        # Agrupa entidades por tipo clinico
        by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for _, row in typed_ents.iterrows():
            etype = str(row["type"]).strip()
            by_type[etype].append(row.to_dict())

        # 2. Executa deduplicacao / clustering hierarquico por tipo
        ent_to_node_id: Dict[str, str] = {}
        type_counters: Dict[str, int] = defaultdict(int)
        clinical_nodes: List[Dict[str, Any]] = []

        # Processa cada tipo na ordem padrao
        ordered_types = sorted(by_type.keys())
        for etype in ordered_types:
            ents_list = by_type[etype]
            clusters = self.clusterer.cluster_entities_of_same_type(ents_list)

            prefix = TYPE_PREFIXES.get(etype, "N")
            for cl in clusters:
                type_counters[prefix] += 1
                nid = f"{prefix}{type_counters[prefix]}"

                # Registra mapeamento ent_id -> node_id
                for eid in cl["entity_ids"]:
                    ent_to_node_id[eid] = nid

                attrs_str = _format_attributes_str(cl["attributes"])
                clinical_nodes.append(
                    {
                        "case_id": case_id,
                        "node_id": nid,
                        "type": etype,
                        "label": cl["label"],
                        "attributes": attrs_str,
                        "concept_code": cl.get("concept_code", ""),
                    }
                )

        # 3. Criacao de nos Concept e arestas SAME_AS
        concept_nodes: List[Dict[str, Any]] = []
        concept_code_to_cid: Dict[str, str] = {}
        concept_counter = 0

        same_as_edges: List[Dict[str, Any]] = []

        for cnode in clinical_nodes:
            code = cnode.get("concept_code", "")
            if code and str(code).strip():
                code_str = str(code).strip()
                if code_str.lower() in {"nan", "none", ""}:
                    continue
                if code_str not in concept_code_to_cid:
                    concept_counter += 1
                    cid = f"C{concept_counter}"
                    concept_code_to_cid[code_str] = cid
                    concept_nodes.append(
                        {
                            "case_id": case_id,
                            "node_id": cid,
                            "type": "Concept",
                            "label": cnode["label"],
                            "attributes": f"code={code_str}",
                        }
                    )
                else:
                    cid = concept_code_to_cid[code_str]

                # Aresta SAME_AS
                same_as_edges.append(
                    {
                        "case_id": case_id,
                        "source_id": cnode["node_id"],
                        "target_id": cid,
                        "relation": "SAME_AS",
                        "attributes": "",
                    }
                )

        # 4. Processamento de arestas clinicas
        clinical_edges: List[Dict[str, Any]] = []
        seen_edges: Set[Tuple[str, str, str]] = set()

        for _, rel_row in case_rels.iterrows():
            src_eid = str(rel_row["source"]).strip()
            tgt_eid = str(rel_row["target"]).strip()
            relation = str(rel_row["relation"]).strip()

            src_nid = ent_to_node_id.get(src_eid)
            tgt_nid = ent_to_node_id.get(tgt_eid)

            if not src_nid or not tgt_nid:
                continue
            if src_nid == tgt_nid:
                continue  # Evita auto-loop resultante de fusao de mencoes

            edge_key = (src_nid, tgt_nid, relation)
            if edge_key in seen_edges:
                continue
            seen_edges.add(edge_key)

            # Atributos da aresta
            edge_attrs: Dict[str, Any] = {}
            if "certainty" in rel_row and pd.notna(rel_row["certainty"]):
                edge_attrs["certainty"] = str(rel_row["certainty"]).strip()
            if "trigger" in rel_row and pd.notna(rel_row["trigger"]):
                edge_attrs["trigger"] = str(rel_row["trigger"]).strip()
            if "evidence_text" in rel_row and pd.notna(rel_row["evidence_text"]):
                edge_attrs["evidence_text"] = str(rel_row["evidence_text"]).strip()
            if "char_start" in rel_row and pd.notna(rel_row["char_start"]):
                edge_attrs["char_start"] = int(rel_row["char_start"])
            if "char_end" in rel_row and pd.notna(rel_row["char_end"]):
                edge_attrs["char_end"] = int(rel_row["char_end"])

            attrs_str = _format_attributes_str(edge_attrs)
            clinical_edges.append(
                {
                    "case_id": case_id,
                    "source_id": src_nid,
                    "target_id": tgt_nid,
                    "relation": relation,
                    "attributes": attrs_str,
                }
            )

        # 5. Consolida tabelas finais
        all_nodes_data = [
            {
                "case_id": n["case_id"],
                "node_id": n["node_id"],
                "type": n["type"],
                "label": n["label"],
                "attributes": n["attributes"],
            }
            for n in clinical_nodes + concept_nodes
        ]
        df_nodes = pd.DataFrame(all_nodes_data)
        if df_nodes.empty:
            df_nodes = pd.DataFrame(
                columns=["case_id", "node_id", "type", "label", "attributes"]
            )

        all_edges_data = []
        edge_id_counter = 0

        for edge in clinical_edges + same_as_edges:
            edge_id_counter += 1
            all_edges_data.append(
                {
                    "case_id": case_id,
                    "edge_id": f"e{edge_id_counter}",
                    "source_id": edge["source_id"],
                    "target_id": edge["target_id"],
                    "relation": edge["relation"],
                    "attributes": edge["attributes"],
                }
            )

        df_edges = pd.DataFrame(all_edges_data)
        if df_edges.empty:
            df_edges = pd.DataFrame(
                columns=[
                    "case_id",
                    "edge_id",
                    "source_id",
                    "target_id",
                    "relation",
                    "attributes",
                ]
            )

        return df_nodes, df_edges
