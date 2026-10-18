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


def resolver_entidade(
    mencoes: List[Dict],
    tipo: str,
    char_start: int,
    char_end: int,
    trigger: str,
    texto_caso: str,
) -> Optional[Dict]:
    """Mencao do tipo certo contida em [char_start, char_end], mais proxima do trigger."""
    candidatas = [
        m for m in mencoes
        if m["tipo"] == tipo and char_start <= m["start"] and m["end"] <= char_end
    ]
    if not candidatas:
        return None
    if len(candidatas) == 1:
        return candidatas[0]
    posicao_trigger = texto_caso.find(trigger, char_start, char_end) if trigger else -1
    referencia = posicao_trigger if posicao_trigger >= 0 else (char_start + char_end) // 2
    return min(candidatas, key=lambda m: abs(((m["start"] + m["end"]) // 2) - referencia))


def resolver_positivos(
    texto_caso: str,
    mencoes: List[Dict],
    tipos_dos_nos: Dict[str, str],
    arestas: List[Dict],
):
    """Resolve cada aresta clinica para um par de mencoes via offset, sem casar texto.

    Retorna (positivos, arestas_descartadas). 'origem' e None quando o lado e
    Patient (nao tem span real - a regra de relacoes.py trata por categoria,
    nao precisa de posicao); 'destino' e sempre uma mencao resolvida.
    """
    positivos: List[Dict] = []
    vistos = set()
    descartadas = 0
    for aresta in arestas:
        tipo_origem = tipos_dos_nos.get(aresta["source_id"])
        tipo_destino = tipos_dos_nos.get(aresta["target_id"])
        if tipo_origem is None or tipo_destino is None:
            descartadas += 1
            continue

        if tipo_origem == "Patient":
            origem, origem_id = None, aresta["source_id"]
        else:
            origem = resolver_entidade(
                mencoes, tipo_origem, aresta["char_start"], aresta["char_end"],
                aresta["trigger"], texto_caso,
            )
            if origem is None:
                descartadas += 1
                continue
            origem_id = origem["id"]

        destino = resolver_entidade(
            mencoes, tipo_destino, aresta["char_start"], aresta["char_end"],
            aresta["trigger"], texto_caso,
        )
        if destino is None:
            descartadas += 1
            continue
        destino_id = destino["id"]

        if origem_id == destino_id:
            descartadas += 1
            continue

        chave = (origem_id, destino_id)
        if chave in vistos:
            continue
        vistos.add(chave)
        positivos.append(
            {
                "source_id": origem_id,
                "target_id": destino_id,
                "source_tipo": tipo_origem,
                "target_tipo": tipo_destino,
                "relation": aresta["relation"],
                "certainty": aresta["certainty"],
                "origem": origem,
                "destino": destino,
            }
        )
    return positivos, descartadas


COLUNAS = [
    "case_id", "source_id", "target_id", "source_text", "target_text",
    "source_type", "target_type", "between_text", "distance_chars",
    "relation", "polarity", "certainty", "is_positive",
]

DISTANCIA_MAXIMA_NEGATIVO = 200


def _texto(texto_caso: str, inicio: int, fim: int) -> str:
    return texto_caso[inicio:fim]


def linha_do_positivo(case_id: str, texto_caso: str, positivo: Dict) -> Dict:
    origem = positivo["origem"]
    destino = positivo["destino"]
    if origem is None:
        source_text, distance_chars, between_text = "", 0, ""
    else:
        source_text = _texto(texto_caso, origem["start"], origem["end"])
        distance_chars = abs(destino["start"] - origem["start"])
        inicio, fim = min(origem["end"], destino["end"]), max(origem["start"], destino["start"])
        between_text = _texto(texto_caso, inicio, fim).strip() if inicio < fim else ""
    return {
        "case_id": case_id,
        "source_id": positivo["source_id"],
        "target_id": positivo["target_id"],
        "source_text": source_text,
        "target_text": _texto(texto_caso, destino["start"], destino["end"]),
        "source_type": positivo["source_tipo"],
        "target_type": positivo["target_tipo"],
        "between_text": between_text,
        "distance_chars": distance_chars,
        "relation": positivo["relation"],
        "polarity": "present",
        "certainty": positivo["certainty"],
        "is_positive": 1,
    }


def linha_negativa(case_id: str, texto_caso: str, m1: Dict, m2: Dict) -> Dict:
    inicio, fim = min(m1["end"], m2["end"]), max(m1["start"], m2["start"])
    between_text = _texto(texto_caso, inicio, fim).strip() if inicio < fim else ""
    return {
        "case_id": case_id,
        "source_id": m1["id"],
        "target_id": m2["id"],
        "source_text": _texto(texto_caso, m1["start"], m1["end"]),
        "target_text": _texto(texto_caso, m2["start"], m2["end"]),
        "source_type": m1["tipo"],
        "target_type": m2["tipo"],
        "between_text": between_text,
        "distance_chars": abs(m2["start"] - m1["start"]),
        "relation": "NONE",
        "polarity": "present",
        "certainty": "asserted",
        "is_positive": 0,
    }


def gerar_pares_do_caso(
    case_id: str,
    texto_caso: str,
    mencoes_path: Path = MENCOES_SILVER,
    processados: Path = PROCESSADOS,
):
    """Linhas (positivas + negativas), estatisticas e mencoes de um caso."""
    mencoes = carregar_mencoes(case_id, mencoes_path)
    if not mencoes:
        return [], {"positivos_resolvidos": 0, "arestas_descartadas": 0}, []

    tipos_dos_nos = carregar_tipos_dos_nos(case_id, processados)
    arestas = carregar_arestas(case_id, processados)
    positivos, descartadas = resolver_positivos(texto_caso, mencoes, tipos_dos_nos, arestas)

    vistos = {(p["source_id"], p["target_id"]) for p in positivos}
    linhas = [linha_do_positivo(case_id, texto_caso, p) for p in positivos]

    for i, m1 in enumerate(mencoes):
        for m2 in mencoes[i + 1:]:
            par = (m1["id"], m2["id"])
            if par in vistos or (m2["id"], m1["id"]) in vistos:
                continue
            if abs(m2["start"] - m1["start"]) > DISTANCIA_MAXIMA_NEGATIVO:
                continue
            linhas.append(linha_negativa(case_id, texto_caso, m1, m2))

    stats = {"positivos_resolvidos": len(positivos), "arestas_descartadas": descartadas}
    return linhas, stats, mencoes
