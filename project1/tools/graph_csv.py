"""Leitura genérica de CSVs no contrato comum (nós/arestas) e do recorte de case_text.

Não importa nada de src/*/core — os pacotes de estratégia têm nomes de módulo
que colidem entre si (ver pipelines/notebooks/grafo_combinado.ipynb), então
este módulo só entende o formato de arquivo (colunas + 'attributes'
serializado), igual a qualquer estratégia que siga o contrato comum.
"""

import csv
import re
from pathlib import Path

NODE_COLUMNS = ("case_id", "node_id", "type", "label", "attributes")
EDGE_COLUMNS = ("case_id", "edge_id", "source_id", "target_id", "relation", "attributes")

# 'serialize_attributes' (repetido em cada estratégia, ex. stopwords/core/models.py)
# junta pares 'chave=valor' com '; ' sem escapar valores que contenham esse
# delimitador (ex.: evidence_text com pontuação). Só quebramos em '; ' quando o
# que vem depois parece uma nova chave (identificador seguido de '='), porque
# nenhuma chave conhecida do contrato comum tem esse formato dentro do valor.
_ATTR_SPLIT_RE = re.compile(r"; (?=[A-Za-z_][A-Za-z0-9_]*=)")


def parse_attributes(raw: str) -> dict[str, str]:
    """Reverte 'chave=valor; chave=valor' para dict. String vazia -> {}."""
    if not raw:
        return {}
    attributes: dict[str, str] = {}
    for part in _ATTR_SPLIT_RE.split(raw):
        key, separator, value = part.partition("=")
        if not separator:
            continue
        attributes[key] = value
    return attributes


def read_case_texts(path: Path) -> dict[str, str]:
    """Lê case_texts.csv (case_id, case_text) -> {case_id: case_text}.

    Arquivo ausente (ex.: alguém rodando local sem tê-lo gerado ainda) não é
    erro fatal: devolve {} e quem chama trata como 'sem case_text'.
    """
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["case_id"]: row["case_text"] for row in csv.DictReader(handle)}


def read_nodes_csv(path: Path) -> list[dict]:
    """Lê <case_id>-nodes.csv -> lista de dicts com attributes já em dict."""
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        {
            "node_id": row["node_id"],
            "type": row["type"],
            "label": row["label"],
            "attributes": parse_attributes(row["attributes"]),
        }
        for row in rows
    ]


def read_edges_csv(path: Path) -> list[dict]:
    """Lê <case_id>-edges.csv -> lista de dicts com attributes já em dict."""
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        {
            "edge_id": row["edge_id"],
            "source_id": row["source_id"],
            "target_id": row["target_id"],
            "relation": row["relation"],
            "attributes": parse_attributes(row["attributes"]),
        }
        for row in rows
    ]
