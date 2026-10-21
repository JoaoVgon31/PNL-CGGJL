"""Módulo oficial de avaliação do Projeto 2 (#29): menções, tipos/polaridade, relações e grafo.

Fornece:
  - `avaliar_mencoes(pred, gold)`: P, R e F1 de fronteiras (`exato` e `sobreposicao`, 1-para-1).
  - `avaliar_tipos(pred, gold, exato)`: cobertura, acurácia, macro F1, P/R/F1 por tipo, matriz
    de confusão e métricas de polaridade (`acuracia_polaridade`, `f1_absent`).
  - `avaliar_relacoes(pred_rel, gold_rel, pred_mencoes, gold_mencoes, exato)`: P, R, F1 global,
    macro F1 e métricas por tipo de relação, casando os extremos pelos spans `(start, end)` das
    menções (ou `P1` quando o extremo é o paciente) — suportando avaliação isolada e ponta a ponta.
  - `avaliar_grafo(pasta_grafos)`: métricas estruturais dos grafos montados (nós, arestas, grau
    médio, % de nós com código MeSH e nós duplicados com o mesmo código MeSH no mesmo caso).
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

Span = tuple[str, int, int]  # (case_id, start, end)
SEM_TIPO = ""



# ==================================================================== 1. Menções ==
def _por_caso(spans: list[Span]) -> dict[str, list[tuple[int, int]]]:
    agrupados: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for case_id, inicio, fim in spans:
        agrupados[case_id].append((int(inicio), int(fim)))
    return agrupados


def _casados(pred: list[Span], gold: list[Span], exato: bool) -> int:
    """Pares um para um: cada menção do gabarito casa com no máximo uma predita."""
    total = 0
    gold_caso = _por_caso(gold)
    for case_id, preditos in _por_caso(pred).items():
        livres = sorted(set(gold_caso.get(case_id, [])))
        for inicio, fim in sorted(set(preditos)):
            for k, (g_ini, g_fim) in enumerate(livres):
                if ((g_ini, g_fim) == (inicio, fim)) if exato else (inicio < g_fim and g_ini < fim):
                    total += 1
                    del livres[k]
                    break
    return total


def avaliar_mencoes(pred: list[Span], gold: list[Span]) -> dict[str, dict[str, float | int]]:
    """{'exato'|'sobreposicao': {precisao, revocacao, f1, n_pred, n_gold, casados}}."""
    n_pred, n_gold = len(set(pred)), len(set(gold))
    saida: dict[str, dict[str, float | int]] = {}
    for modo, exato in (("exato", True), ("sobreposicao", False)):
        casados = _casados(pred, gold, exato)
        p = casados / n_pred if n_pred else 0.0
        r = casados / n_gold if n_gold else 0.0
        saida[modo] = {
            "precisao": p,
            "revocacao": r,
            "f1": 2 * p * r / (p + r) if p + r else 0.0,
            "n_pred": n_pred,
            "n_gold": n_gold,
            "casados": casados,
        }
    return saida


# ======================================================== 2. Tipos e Polaridade ==
def parear(
    pred: list[dict[str, Any]],
    gold: list[dict[str, Any]],
    exato: bool = True,
) -> list[tuple[dict[str, Any] | None, dict[str, Any] | None]]:
    """Pares (predita, gold) um para um; quem sobra vem com o outro lado None."""
    gold_caso: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for g in gold:
        gold_caso[g["case_id"]].append(g)
    usados: set[int] = set()
    pares: list[tuple[dict[str, Any] | None, dict[str, Any] | None]] = []
    for p in sorted(pred, key=lambda m: (m["case_id"], int(m["start"]), int(m["end"]))):
        p_ini, p_fim = int(p["start"]), int(p["end"])
        for g in gold_caso.get(p["case_id"], []):
            if id(g) in usados:
                continue
            g_ini, g_fim = int(g["start"]), int(g["end"])
            if ((g_ini, g_fim) == (p_ini, p_fim)) if exato else (p_ini < g_fim and g_ini < p_fim):
                usados.add(id(g))
                pares.append((p, g))
                break
        else:
            pares.append((p, None))
    pares += [(None, g) for g in gold if id(g) not in usados]
    return pares


def avaliar_tipos(
    pred: list[dict[str, Any]],
    gold: list[dict[str, Any]],
    exato: bool = True,
) -> dict[str, Any]:
    """{cobertura, acuracia, macro_f1, acuracia_polaridade, f1_absent, n_gold, n_pred, por_tipo, confusao}."""
    pares = parear(pred, gold, exato)
    acertos: Counter[str] = Counter()
    preditos: Counter[str] = Counter()
    no_gold: Counter[str] = Counter()
    confusao: Counter[tuple[str, str]] = Counter()

    pol_acertos = 0
    pol_total = 0
    tp_absent = fp_absent = fn_absent = 0

    for p, g in pares:
        tipo_p = (p.get("tipo") or SEM_TIPO) if p else SEM_TIPO
        if tipo_p != SEM_TIPO:
            preditos[tipo_p] += 1
        if g is None:
            continue
        tipo_g = g["tipo"]
        no_gold[tipo_g] += 1
        confusao[(tipo_g, tipo_p)] += 1
        if tipo_p == tipo_g:
            acertos[tipo_g] += 1

        if p is not None and ("polaridade" in g or "polaridade" in p):
            pol_g = str(g.get("polaridade") or "present").strip()
            pol_p = str(p.get("polaridade") or "present").strip()
            pol_total += 1
            if pol_g == pol_p:
                pol_acertos += 1
            if pol_g == "absent" and pol_p == "absent":
                tp_absent += 1
            elif pol_g != "absent" and pol_p == "absent":
                fp_absent += 1
            elif pol_g == "absent" and pol_p != "absent":
                fn_absent += 1

    por_tipo: dict[str, dict[str, float | int]] = {}
    for tipo in sorted(no_gold):
        p_t = acertos[tipo] / preditos[tipo] if preditos[tipo] else 0.0
        r_t = acertos[tipo] / no_gold[tipo]
        por_tipo[tipo] = {
            "precisao": p_t,
            "revocacao": r_t,
            "f1": 2 * p_t * r_t / (p_t + r_t) if p_t + r_t else 0.0,
            "n": no_gold[tipo],
        }
    n_gold = sum(no_gold.values())
    tipados = sum(v for (_, tp), v in confusao.items() if tp != SEM_TIPO)
    acuracia_polaridade = pol_acertos / pol_total if pol_total else 0.0
    denom_absent = 2 * tp_absent + fp_absent + fn_absent
    f1_absent = (2 * tp_absent / denom_absent) if denom_absent else 0.0

    return {
        "cobertura": tipados / n_gold if n_gold else 0.0,
        "acuracia": sum(acertos.values()) / n_gold if n_gold else 0.0,
        "macro_f1": sum(float(m["f1"]) for m in por_tipo.values()) / len(por_tipo) if por_tipo else 0.0,
        "acuracia_polaridade": acuracia_polaridade,
        "f1_absent": f1_absent,
        "n_gold": n_gold,
        "n_pred": len(pred),
        "por_tipo": por_tipo,
        "confusao": dict(confusao),
    }


# ================================================================== 3. Relações ==
EndpointSpan = tuple[int, int]  # (-1, -1) para o nó Patient (P1)
PACIENTE_SPAN: EndpointSpan = (-1, -1)


def _mapa_spans_mencoes(mencoes: list[dict[str, Any]]) -> dict[tuple[str, str], EndpointSpan]:
    """(case_id, id) -> (start, end); inclui P1 como (-1, -1) e entidades do tipo Patient."""
    mapa: dict[tuple[str, str], EndpointSpan] = {}
    for m in mencoes:
        cid = str(m["case_id"])
        mid = str(m.get("id") or m.get("mention_id") or m.get("ent_id") or "")
        tipo = str(m.get("tipo") or m.get("type") or "")
        if mid == "P1" or tipo == "Patient":
            mapa[(cid, mid)] = PACIENTE_SPAN
        else:
            ini = int(m.get("start") if "start" in m else m["char_start"])
            fim = int(m.get("end") if "end" in m else m["char_end"])
            mapa[(cid, mid)] = (ini, fim)
    return mapa


def _resolver_extremo(
    case_id: str,
    ident: str,
    mapa: dict[tuple[str, str], EndpointSpan],
) -> EndpointSpan | None:
    if ident == "P1":
        return PACIENTE_SPAN
    return mapa.get((case_id, ident))


def _extremos_casam(a: EndpointSpan, b: EndpointSpan, exato: bool) -> bool:
    if a == PACIENTE_SPAN or b == PACIENTE_SPAN:
        return a == b
    if exato:
        return a == b
    return a[0] < b[1] and b[0] < a[1]


def avaliar_relacoes(
    pred_rel: list[dict[str, Any]],
    gold_rel: list[dict[str, Any]],
    pred_mencoes: list[dict[str, Any]],
    gold_mencoes: list[dict[str, Any]],
    exato: bool = True,
) -> dict[str, Any]:
    """Avalia relações casando os extremos pelos spans (start, end) das menções (ou P1).

    Funciona tanto no modo isolado (`pred_mencoes == gold_mencoes`) quanto no modo
    ponta a ponta (`pred_mencoes` vindo do CRF e `gold_mencoes` vindo do gabarito).
    """
    mapa_p = _mapa_spans_mencoes(pred_mencoes)
    mapa_g = _mapa_spans_mencoes(gold_mencoes)

    # Normaliza cada relação para (case_id, span_origem, span_destino, relacao)
    pred_por_caso: dict[str, list[tuple[EndpointSpan, EndpointSpan, str]]] = defaultdict(list)
    for r in pred_rel:
        cid = str(r["case_id"])
        orig = str(r.get("origem") or r.get("source") or "")
        dest = str(r.get("destino") or r.get("target") or "")
        rel = str(r.get("relacao") or r.get("relation") or "")
        if not rel or rel == "NONE":
            continue
        sp_o = _resolver_extremo(cid, orig, mapa_p)
        sp_d = _resolver_extremo(cid, dest, mapa_p)
        if sp_o is not None and sp_d is not None:
            pred_por_caso[cid].append((sp_o, sp_d, rel))

    gold_por_caso: dict[str, list[tuple[EndpointSpan, EndpointSpan, str]]] = defaultdict(list)
    for r in gold_rel:
        cid = str(r["case_id"])
        orig = str(r.get("origem") or r.get("source") or "")
        dest = str(r.get("destino") or r.get("target") or "")
        rel = str(r.get("relacao") or r.get("relation") or "")
        if not rel or rel == "NONE":
            continue
        sp_o = _resolver_extremo(cid, orig, mapa_g)
        sp_d = _resolver_extremo(cid, dest, mapa_g)
        if sp_o is not None and sp_d is not None:
            gold_por_caso[cid].append((sp_o, sp_d, rel))

    acertos: Counter[str] = Counter()
    preditos: Counter[str] = Counter()
    no_gold: Counter[str] = Counter()

    todos_casos = sorted(set(pred_por_caso) | set(gold_por_caso))
    for cid in todos_casos:
        livres = list(dict.fromkeys(gold_por_caso.get(cid, [])))
        for _, _, rel_g in livres:
            no_gold[rel_g] += 1
        for sp_op, sp_dp, rel_p in list(dict.fromkeys(pred_por_caso.get(cid, []))):
            preditos[rel_p] += 1
            for k, (sp_og, sp_dg, rel_g) in enumerate(livres):
                if (
                    rel_p == rel_g
                    and _extremos_casam(sp_op, sp_og, exato)
                    and _extremos_casam(sp_dp, sp_dg, exato)
                ):
                    acertos[rel_p] += 1
                    del livres[k]
                    break

    n_pred = sum(preditos.values())
    n_gold = sum(no_gold.values())
    casados = sum(acertos.values())
    p_global = casados / n_pred if n_pred else 0.0
    r_global = casados / n_gold if n_gold else 0.0
    f1_global = 2 * p_global * r_global / (p_global + r_global) if p_global + r_global else 0.0

    por_relacao: dict[str, dict[str, float | int]] = {}
    for rel in sorted(no_gold):
        pr = acertos[rel] / preditos[rel] if preditos[rel] else 0.0
        rc = acertos[rel] / no_gold[rel] if no_gold[rel] else 0.0
        por_relacao[rel] = {
            "precisao": pr,
            "revocacao": rc,
            "f1": 2 * pr * rc / (pr + rc) if pr + rc else 0.0,
            "n": no_gold[rel],
        }
    macro_f1 = (
        sum(float(m["f1"]) for m in por_relacao.values()) / len(por_relacao)
        if por_relacao
        else 0.0
    )

    return {
        "precisao": p_global,
        "revocacao": r_global,
        "f1": f1_global,
        "macro_f1": macro_f1,
        "n_pred": n_pred,
        "n_gold": n_gold,
        "casados": casados,
        "por_relacao": por_relacao,
    }


# ========================================================== 4. Grafo Estrutural ==
def _parse_attrs(bruto: str | None) -> dict[str, str]:
    if not bruto:
        return {}
    saida: dict[str, str] = {}
    for parte in str(bruto).split("; "):
        if "=" in parte:
            k, v = parte.split("=", 1)
            saida[k.strip()] = v.strip()
    return saida


def avaliar_grafo(pasta_grafos: Path, casos: set[str] | None = None) -> dict[str, Any]:
    """Métricas estruturais sobre `<case_id>-nodes.csv` e `<case_id>-edges.csv` (#29).

    Calcula:
      - número de casos, nós e arestas (totais e médias por caso)
      - grau médio dos nós
      - proporção de nós clínicos (exceto Patient e Concept) vinculados a código MeSH/Concept
      - número de nós clínicos duplicados que compartilham o mesmo `(type, code)` no mesmo caso
    """
    arquivos_nos = sorted(Path(pasta_grafos).glob("*-nodes.csv"))
    if casos is not None:
        arquivos_nos = [p for p in arquivos_nos if p.name[:-10] in casos]

    n_casos = 0
    total_nos = 0
    total_arestas = 0
    nos_clinicos = 0
    nos_clinicos_com_mesh = 0
    nos_duplicados_mesmo_mesh = 0

    for arq_nos in arquivos_nos:
        case_id = arq_nos.name[:-10]
        arq_arestas = arq_nos.parent / f"{case_id}-edges.csv"
        if not arq_arestas.is_file():
            continue
        with open(arq_nos, encoding="utf-8", newline="") as h_n:
            nos = list(csv.DictReader(h_n))
        with open(arq_arestas, encoding="utf-8", newline="") as h_e:
            arestas = list(csv.DictReader(h_e))

        n_casos += 1
        total_nos += len(nos)
        total_arestas += len(arestas)

        codigos_concept: dict[str, str] = {}
        for n in nos:
            if n["type"] == "Concept":
                attrs = _parse_attrs(n.get("attributes", ""))
                if attrs.get("code"):
                    codigos_concept[n["node_id"]] = attrs["code"]

        mesh_por_no: dict[str, str] = {}
        for e in arestas:
            if e["relation"] == "SAME_AS" and e["target_id"] in codigos_concept:
                mesh_por_no[e["source_id"]] = codigos_concept[e["target_id"]]

        contagem_tipo_mesh: Counter[tuple[str, str]] = Counter()
        for n in nos:
            tipo = n["type"]
            if tipo in ("Patient", "Concept"):
                continue
            nos_clinicos += 1
            nid = n["node_id"]
            attrs = _parse_attrs(n.get("attributes", ""))
            codigo = mesh_por_no.get(nid) or attrs.get("code", "")
            if codigo:
                nos_clinicos_com_mesh += 1
                contagem_tipo_mesh[(tipo, codigo)] += 1

        nos_duplicados_mesmo_mesh += sum(c - 1 for c in contagem_tipo_mesh.values() if c > 1)

    grau_medio = (2.0 * total_arestas / total_nos) if total_nos else 0.0
    pct_mesh = (nos_clinicos_com_mesh / nos_clinicos) if nos_clinicos else 0.0
    return {
        "n_casos": n_casos,
        "n_nos": total_nos,
        "n_arestas": total_arestas,
        "media_nos_por_caso": round(total_nos / n_casos, 2) if n_casos else 0.0,
        "media_arestas_por_caso": round(total_arestas / n_casos, 2) if n_casos else 0.0,
        "grau_medio": round(grau_medio, 4),
        "nos_clinicos": nos_clinicos,
        "nos_clinicos_com_mesh": nos_clinicos_com_mesh,
        "pct_nos_com_mesh": round(pct_mesh, 4),
        "nos_duplicados_mesmo_mesh": nos_duplicados_mesmo_mesh,
    }


def _ler_csv(caminho: Path) -> list[dict[str, Any]]:
    with open(caminho, encoding="utf-8", newline="") as handle:
        linhas = list(csv.DictReader(handle))
    for linha in linhas:
        if "start" in linha and linha["start"] != "":
            linha["start"] = int(linha["start"])
        if "end" in linha and linha["end"] != "":
            linha["end"] = int(linha["end"])
    return linhas


def consolidar(raiz_repo: Path | None = None) -> dict[str, Any]:
    """Consolida montagem.csv e comparativo_p1_p2.csv em project2/data/resultados/."""
    from project2.src.comum import REPO, casos_gold

    repo = raiz_repo or REPO
    res_dir = repo / "project2" / "data" / "resultados"
    res_dir.mkdir(parents=True, exist_ok=True)
    gold_ids = set(casos_gold())

    p1_todos = avaliar_grafo(repo / "project1" / "data" / "processed")
    p2_todos = avaliar_grafo(repo / "project2" / "data" / "grafo")
    p1_gold = avaliar_grafo(repo / "project1" / "data" / "processed", casos=gold_ids)
    p2_gold = avaliar_grafo(repo / "project2" / "data" / "grafo", casos=gold_ids)

    linhas_montagem = [
        {"sistema": "Projeto 1 (regras)", "recorte": "56_casos", **p1_todos},
        {"sistema": "Projeto 2 (pipeline)", "recorte": "56_casos", **p2_todos},
        {"sistema": "Projeto 1 (regras)", "recorte": "8_casos_gold", **p1_gold},
        {"sistema": "Projeto 2 (pipeline)", "recorte": "8_casos_gold", **p2_gold},
    ]
    with open(res_dir / "montagem.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(linhas_montagem[0].keys()))
        w.writeheader()
        w.writerows(linhas_montagem)

    # Tabela unificada P1 vs P2 nos 8 casos gold
    ent_rows = _ler_csv(res_dir / "entidades.csv")
    tip_rows = _ler_csv(res_dir / "tipos.csv")
    rel_rows = [r for r in _ler_csv(res_dir / "relacoes.csv") if r["relacao"] == "GLOBAL"]

    def _find(rows: list[dict], **conds: str) -> dict:
        for r in rows:
            if all(str(r.get(k)) == v for k, v in conds.items()):
                return r
        return {}

    e_p1_ex = _find(ent_rows, sistema="regras P1", casamento="exato")
    e_p1_sb = _find(ent_rows, sistema="regras P1", casamento="sobreposicao")
    e_bio_ex = _find(ent_rows, sistema="só pos_bio", casamento="exato")
    e_bio_sb = _find(ent_rows, sistema="só pos_bio", casamento="sobreposicao")
    e_crf_ex = _find(ent_rows, sistema="CRF + termos", casamento="exato")
    e_crf_sb = _find(ent_rows, sistema="CRF + termos", casamento="sobreposicao")

    t_p1_ex = _find(tip_rows, sistema="regras P1", entrada="regras", casamento="exato")
    t_p1_sb = _find(tip_rows, sistema="regras P1", entrada="regras", casamento="sobreposicao")
    t_iso_ex = _find(tip_rows, sistema="lexico+classificador", entrada="gabarito", casamento="exato")
    t_e2e_ex = _find(tip_rows, sistema="lexico+classificador", entrada="crf", casamento="exato")
    t_e2e_sb = _find(tip_rows, sistema="lexico+classificador", entrada="crf", casamento="sobreposicao")

    r_p1_ex = _find(rel_rows, sistema="regras P1", entrada="regras P1", criterio="exato")
    r_p1_sb = _find(rel_rows, sistema="regras P1", entrada="regras P1", criterio="sobreposicao")
    r_iso_ex = _find(rel_rows, sistema="LR (1-2)", entrada="gabarito", criterio="exato")
    r_e2e_ex = _find(rel_rows, sistema="LR (1-2)", entrada="crf+tipos", criterio="exato")
    r_e2e_sb = _find(rel_rows, sistema="LR (1-2)", entrada="crf+tipos", criterio="sobreposicao")

    comparativo = [
        {
            "etapa": "Etapa 2 - Fronteiras de Mencoes",
            "modo": "ponta_a_ponta",
            "criterio": "exato",
            "p1_sistema": "regras P1",
            "p1_f1": e_p1_ex.get("f1", ""),
            "p2_sistema": "CRF + termos (pos_bio)",
            "p2_f1": f"{e_crf_ex.get('f1', '')} (pos_bio={e_bio_ex.get('f1', '')})",
        },
        {
            "etapa": "Etapa 2 - Fronteiras de Mencoes",
            "modo": "ponta_a_ponta",
            "criterio": "sobreposicao",
            "p1_sistema": "regras P1",
            "p1_f1": e_p1_sb.get("f1", ""),
            "p2_sistema": "CRF + termos (pos_bio)",
            "p2_f1": f"{e_crf_sb.get('f1', '')} (pos_bio={e_bio_sb.get('f1', '')})",
        },
        {
            "etapa": "Etapa 3 - Tipagem Semantica (Macro-F1)",
            "modo": "isolado (gabarito)",
            "criterio": "exato",
            "p1_sistema": "regras P1",
            "p1_f1": t_p1_ex.get("macro_f1", ""),
            "p2_sistema": "lexico + modelo",
            "p2_f1": t_iso_ex.get("macro_f1", ""),
        },
        {
            "etapa": "Etapa 3 - Tipagem Semantica (Macro-F1)",
            "modo": "ponta_a_ponta (crf)",
            "criterio": "sobreposicao",
            "p1_sistema": "regras P1",
            "p1_f1": t_p1_sb.get("macro_f1", ""),
            "p2_sistema": "lexico + modelo",
            "p2_f1": t_e2e_sb.get("macro_f1", ""),
        },
        {
            "etapa": "Etapa 3 - Polaridade (Acuracia / F1 absent)",
            "modo": "isolado (gabarito)",
            "criterio": "exato",
            "p1_sistema": "regras P1",
            "p1_f1": f"acc={t_p1_ex.get('acuracia_polaridade', '')} / f1_abs={t_p1_ex.get('f1_absent', '')}",
            "p2_sistema": "lexico + modelo (clausula)",
            "p2_f1": f"acc={t_iso_ex.get('acuracia_polaridade', '')} / f1_abs={t_iso_ex.get('f1_absent', '')}",
        },
        {
            "etapa": "Etapa 4 - Extracao de Relacoes (F1 Global)",
            "modo": "isolado (gabarito)",
            "criterio": "exato",
            "p1_sistema": "regras P1",
            "p1_f1": r_p1_ex.get("f1", ""),
            "p2_sistema": "LR (1-2) + regra Patient",
            "p2_f1": r_iso_ex.get("f1", ""),
        },
        {
            "etapa": "Etapa 4 - Extracao de Relacoes (F1 Global)",
            "modo": "ponta_a_ponta (crf+tipos)",
            "criterio": "sobreposicao",
            "p1_sistema": "regras P1",
            "p1_f1": r_p1_sb.get("f1", ""),
            "p2_sistema": "LR (1-2) + regra Patient",
            "p2_f1": r_e2e_sb.get("f1", ""),
        },
        {
            "etapa": "Etapa 5 - Grafo Estrutural (% Nos c/ MeSH | Duplicados)",
            "modo": "56_casos",
            "criterio": "estrutural",
            "p1_sistema": "Projeto 1 (regras)",
            "p1_f1": f"{p1_todos['pct_nos_com_mesh']:.4f} | dup={p1_todos['nos_duplicados_mesmo_mesh']}",
            "p2_sistema": "Projeto 2 (montagem.py)",
            "p2_f1": f"{p2_todos['pct_nos_com_mesh']:.4f} | dup={p2_todos['nos_duplicados_mesmo_mesh']}",
        },
    ]
    with open(res_dir / "comparativo_p1_p2.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(comparativo[0].keys()))
        w.writeheader()
        w.writerows(comparativo)

    return {"montagem": linhas_montagem, "comparativo": comparativo}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="comando", required=True)

    p_menc = sub.add_parser("mencoes", help="Avalia fronteiras de menções (exato e sobreposição)")
    p_menc.add_argument("--pred", type=Path, required=True)
    p_menc.add_argument("--gold", type=Path, required=True)

    p_tipos = sub.add_parser("tipos", help="Avalia tipagem e polaridade das menções")
    p_tipos.add_argument("--pred", type=Path, required=True)
    p_tipos.add_argument("--gold", type=Path, required=True)
    p_tipos.add_argument("--sobreposicao", action="store_true")

    p_rel = sub.add_parser("relacoes", help="Avalia relações pelos spans das menções")
    p_rel.add_argument("--pred", type=Path, required=True)
    p_rel.add_argument("--gold", type=Path, required=True)
    p_rel.add_argument("--mencoes-pred", type=Path, required=True)
    p_rel.add_argument("--mencoes-gold", type=Path, required=True)
    p_rel.add_argument("--sobreposicao", action="store_true")

    p_grafo = sub.add_parser("grafo", help="Métricas estruturais de uma pasta de grafos")
    p_grafo.add_argument("--pasta", type=Path, required=True)

    sub.add_parser("consolidar", help="Gera resultados/montagem.csv e resultados/comparativo_p1_p2.csv")

    args = parser.parse_args()
    if args.comando == "mencoes":
        pred = [(l["case_id"], l["start"], l["end"]) for l in _ler_csv(args.pred)]
        gold = [(l["case_id"], l["start"], l["end"]) for l in _ler_csv(args.gold)]
        print(json.dumps(avaliar_mencoes(pred, gold), indent=2, ensure_ascii=False))
    elif args.comando == "tipos":
        res = avaliar_tipos(_ler_csv(args.pred), _ler_csv(args.gold), exato=not args.sobreposicao)
        res["confusao"] = {f"{g}->{p or '(sem tipo)'}": n for (g, p), n in res["confusao"].items()}
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif args.comando == "relacoes":
        res = avaliar_relacoes(
            _ler_csv(args.pred),
            _ler_csv(args.gold),
            _ler_csv(args.mencoes_pred),
            _ler_csv(args.mencoes_gold),
            exato=not args.sobreposicao,
        )
        print(json.dumps(res, indent=2, ensure_ascii=False))
    elif args.comando == "grafo":
        print(json.dumps(avaliar_grafo(args.pasta), indent=2, ensure_ascii=False))
    elif args.comando == "consolidar":
        print(json.dumps(consolidar(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

