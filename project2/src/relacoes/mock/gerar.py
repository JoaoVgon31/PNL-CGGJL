# -*- coding: utf-8 -*-
"""Gerador de dados mock da Etapa 4: pares de relacao com features, a partir
das mencoes tipadas da Etapa 2 (#33) e das arestas do Projeto 1.

Resolve cada relacao do Projeto 1 contra uma mencao real via sobreposicao de
offset de caractere + tipo - nunca via casamento de texto (rotulo do no x
texto do chunk), que e o que torna o weak_supervision.py do George fragil
para boa parte dos casos (ver docs/superpowers/specs/2026-10-18-relacoes-mock-main-design.md).
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Optional

from project2.src.relacoes.mock import comum

REPO_ROOT = comum.REPO
MENCOES_SILVER = REPO_ROOT / "project2" / "data" / "mock" / "silver" / "mencoes.csv"
PROCESSADOS = REPO_ROOT / "project1" / "data" / "processed"
SAIDA = REPO_ROOT / "project2" / "data" / "mock" / "relacoes"


def parse_attributes(bruto: Optional[str]) -> Dict[str, str]:
    """'k1=v1; k2=v2' -> {"k1": "v1", "k2": "v2"}."""
    if not bruto:
        return {}
    resultado: Dict[str, str] = {}
    for parte in bruto.split("; "):
        if "=" in parte:
            chave, valor = parte.split("=", 1)
            resultado[chave.strip()] = valor.strip()
    return resultado


def carregar_mencoes(case_id: str, mencoes_path: Path = MENCOES_SILVER) -> List[Dict]:
    """Mencoes do caso (id, start, end, texto, tipo), com start/end como int."""
    with open(mencoes_path, encoding="utf-8", newline="") as handle:
        linhas = [l for l in csv.DictReader(handle) if l["case_id"] == case_id]
    for linha in linhas:
        linha["start"] = int(linha["start"])
        linha["end"] = int(linha["end"])
    return linhas


def carregar_tipos_dos_nos(case_id: str, processados: Path = PROCESSADOS) -> Dict[str, str]:
    """node_id -> type, do nodes.csv do Projeto 1."""
    caminho = processados / f"{case_id}-nodes.csv"
    with open(caminho, encoding="utf-8", newline="") as handle:
        return {linha["node_id"]: linha["type"] for linha in csv.DictReader(handle)}


def carregar_arestas(case_id: str, processados: Path = PROCESSADOS) -> List[Dict]:
    """Arestas clinicas (nao-SAME_AS, com offset de evidencia) do caso."""
    caminho = processados / f"{case_id}-edges.csv"
    arestas: List[Dict] = []
    with open(caminho, encoding="utf-8", newline="") as handle:
        for linha in csv.DictReader(handle):
            if linha["relation"] == "SAME_AS":
                continue
            attrs = parse_attributes(linha["attributes"])
            if "char_start" not in attrs or "char_end" not in attrs:
                continue
            arestas.append(
                {
                    "source_id": linha["source_id"],
                    "target_id": linha["target_id"],
                    "relation": linha["relation"],
                    "certainty": attrs.get("certainty", "asserted"),
                    "char_start": int(attrs["char_start"]),
                    "char_end": int(attrs["char_end"]),
                    "trigger": attrs.get("trigger", ""),
                }
            )
    return arestas
