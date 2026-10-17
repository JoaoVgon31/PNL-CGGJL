# -*- coding: utf-8 -*-
"""Agrupamento hierarquico de mencoes clinicas e deduplicacao de nos.

Implementa a diretriz "Um no por coisa" do Projeto 2:
  - Normalizacao de rotulos e extracao de dimensoes/atributos (ex: '6cm cystic lesion' -> size=6 cm).
  - Vetorizacao por TF-IDF de N-gramas de caracteres.
  - Agrupamento hierarquico / similaridade combinada (cosseno + contencao de radical).
  - Fusao de mencoes coreferentes do mesmo tipo clinico em um unico no canonico.
"""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DETERMINERS_PATTERN = re.compile(r"^(?:the|a|an|this|that|these|those)\s+", re.IGNORECASE)
SIZE_PATTERN = re.compile(
    r"^(?:(?:\d+(?:\.\d+)?|\d+/\d+)\s*(?:cm|mm|m)\s*(?:x\s*(?:\d+(?:\.\d+)?|\d+/\d+)\s*(?:cm|mm|m))*\s*)",
    re.IGNORECASE,
)
PUNCT_EDGES = " \t\n\r.,;:!?\"'`()[]{}"


def normalize_label(text: str) -> str:
    """Aplica normalizacao Unicode NFKC, remove pontuacao externa e determinantes."""
    if not isinstance(text, str):
        return ""
    norm = unicodedata.normalize("NFKC", text).strip(PUNCT_EDGES)
    norm = re.sub(r"\s+", " ", norm)
    # Remove determinantes iniciais ("the cyst" -> "cyst")
    norm = DETERMINERS_PATTERN.sub("", norm).strip()
    return norm


def extract_attributes_from_mention(raw_text: str) -> Tuple[str, Dict[str, str]]:
    """Extrai dimensoes e metricas do rotulo, retornando o rotulo limpo e os atributos."""
    cleaned = normalize_label(raw_text)
    attrs: Dict[str, str] = {}

    m_size = SIZE_PATTERN.match(cleaned)
    if m_size:
        size_val = m_size.group(0).strip()
        # Formata com espaco padrao ("6cm" -> "6 cm")
        size_val = re.sub(r"(\d+)(cm|mm|m)", r"\1 \2", size_val, flags=re.IGNORECASE)
        attrs["size"] = size_val
        cleaned = cleaned[len(m_size.group(0)) :].strip()

    cleaned = cleaned.strip(PUNCT_EDGES)
    return cleaned, attrs


class HierarchicalMentionClusterer:
    """Agrupador hierarquico de mencoes clinicas baseado em TF-IDF de N-gramas."""

    def __init__(
        self,
        similarity_threshold: float = 0.55,
        ngram_range: Tuple[int, int] = (2, 4),
    ):
        self.similarity_threshold = similarity_threshold
        self.ngram_range = ngram_range

    def _compute_pairwise_similarity(self, labels: List[str]) -> np.ndarray:
        """Calcula matriz de similaridade entre rotulos combinando TF-IDF e contencao."""
        n = len(labels)
        if n == 0:
            return np.zeros((0, 0))
        if n == 1:
            return np.ones((1, 1))

        # 1. Similaridade por TF-IDF de N-gramas de caracteres
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=self.ngram_range)
        try:
            X = vec.fit_transform(labels)
            sim_tfidf = cosine_similarity(X)
        except ValueError:
            sim_tfidf = np.eye(n)

        # 2. Reforco de similaridade para contencao de substrings ou radicais
        # Ex: "cyst" e "cystic lesion" -> "cyst" esta dentro de "cystic"
        final_sim = np.copy(sim_tfidf)
        for i in range(n):
            for j in range(i + 1, n):
                l1 = labels[i].lower()
                l2 = labels[j].lower()

                # Palavras individuais
                w1 = set(l1.split())
                w2 = set(l2.split())
                jaccard_words = len(w1 & w2) / max(len(w1 | w2), 1)

                # Verifica se uma expressao comeca com o radical da outra
                is_stem_match = any(
                    word.startswith(l1) or l1.startswith(word) for word in w2
                ) or any(word.startswith(l2) or l2.startswith(word) for word in w1)

                if jaccard_words >= 0.5 or (is_stem_match and len(min(l1, l2)) >= 3):
                    # Eleva a similaridade para permitir fusao
                    final_sim[i, j] = max(final_sim[i, j], 0.70)
                    final_sim[j, i] = final_sim[i, j]

        return final_sim

    def cluster_entities_of_same_type(
        self, entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Agrupa uma lista de entidades do mesmo tipo clinico em nos consolidados."""
        if not entities:
            return []

        # Extrai rotulos normalizados e atributos individuais
        clean_labels = []
        entity_attrs = []
        for e in entities:
            lbl, att = extract_attributes_from_mention(e["texto"])
            clean_labels.append(lbl if lbl else e["texto"])
            entity_attrs.append(att)

        n = len(entities)
        if n == 1:
            # Caso trivial: apenas 1 entidade
            e0 = entities[0]
            attrs_dict = dict(entity_attrs[0])
            if "polarity" in e0 and e0["polarity"]:
                attrs_dict["polarity"] = e0["polarity"]
            attrs_dict["mentions"] = str(e0["ent_id"])
            return [
                {
                    "label": clean_labels[0],
                    "type": e0["type"],
                    "concept_code": e0.get("concept_code", ""),
                    "attributes": attrs_dict,
                    "entity_ids": [str(e0["ent_id"])],
                }
            ]

        # Matriz de similaridade
        sim_mat = self._compute_pairwise_similarity(clean_labels)

        # Agrupamento conexo / hierarquico (Union-Find) com threshold
        parent = list(range(n))

        def find(i):
            if parent[i] == i:
                return i
            parent[i] = find(parent[i])
            return parent[i]

        def union(i, j):
            root_i = find(i)
            root_j = find(j)
            if root_i != root_j:
                parent[root_i] = root_j

        for i in range(n):
            for j in range(i + 1, n):
                if sim_mat[i, j] >= self.similarity_threshold:
                    union(i, j)

        # Agrupa itens pelo root do cluster
        clusters_map: Dict[int, List[int]] = defaultdict(list)
        for idx in range(n):
            clusters_map[find(idx)].append(idx)

        consolidated_nodes = []
        for root_idx, member_indices in clusters_map.items():
            member_ents = [entities[m] for m in member_indices]
            member_labels = [clean_labels[m] for m in member_indices]

            # Escolhe o rotulo mais informativo:
            # 1. Se houver conceito MeSH, da preferencia ao termo MeSH ou ao rotulo mais longo/rico
            sorted_labels = sorted(
                member_labels,
                key=lambda s: (len(s.split()), len(s)),
                reverse=True,
            )
            canonical_label = sorted_labels[0]

            # Consolida atributos (tamanho, mencoes, polaridade)
            merged_attrs: Dict[str, str] = {}
            for m in member_indices:
                merged_attrs.update(entity_attrs[m])

            # Verifica polaridade do cluster (se algum for absent, marca absent)
            polarities = {e.get("polarity") for e in member_ents if e.get("polarity")}
            if "absent" in polarities:
                merged_attrs["polarity"] = "absent"
            elif "present" in polarities:
                merged_attrs["polarity"] = "present"

            # Registra todas as mencoes originais (ex: t2|t7)
            mentions_str = "|".join(str(e["ent_id"]) for e in member_ents)
            merged_attrs["mentions"] = mentions_str

            # Concept code (primeiro nao-vazio encontrado no cluster)
            c_code = ""
            for e in member_ents:
                if e.get("concept_code"):
                    c_code = str(e["concept_code"]).strip()
                    break

            consolidated_nodes.append(
                {
                    "label": canonical_label,
                    "type": member_ents[0]["type"],
                    "concept_code": c_code,
                    "attributes": merged_attrs,
                    "entity_ids": [str(e["ent_id"]) for e in member_ents],
                }
            )

        return consolidated_nodes
