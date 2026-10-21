"""Converte menções tipadas e relações no contrato CSV do visualizador do projeto 1."""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from project2.src.comum import CASOS_PADRAO, REPO, casos_gold, dividir_frases, iter_registros
from project1.src.stopwords.extractors.common import detect_polarity
from project1.src.tokenizacao.models import NODE_PREFIXES, serialize_attributes
from project1.tools.graph_csv import read_edges_csv, read_nodes_csv

TIPOS = set(NODE_PREFIXES) - {"Patient", "Concept"}
DOMINIO = {
    "HAS_SYMPTOM": ({"Patient"}, {"Symptom"}),
    "HAS_HISTORY": ({"Patient"}, {"History"}),
    "UNDERWENT_EXAM": ({"Patient"}, {"Exam"}),
    "HAS_FINDING": ({"Patient"}, {"Finding"}),
    "DIAGNOSED_WITH": ({"Patient"}, {"Diagnosis"}),
    "TREATED_WITH": ({"Patient", "Diagnosis"}, {"Treatment", "Medication"}),
    "HAS_OUTCOME": ({"Patient"}, {"Outcome"}),
    "HAS_RESULT": ({"Exam"}, {"ExamResult"}),
    "REVEALS": ({"Exam", "Treatment"}, {"Finding"}),
    "SUPPORTS": ({"Symptom", "Finding", "ExamResult", "History"}, {"Diagnosis"}),
    "LOCATED_IN": ({"Symptom", "Finding", "Treatment"}, {"AnatomicalSite"}),
}
_NUMERO = r"(?:\d+(?:\.\d+)?|\.\d+)"
_UNIDADE = r"\s*(?:[-–—−]\s*)?(?:mm|cm)"
_DIMENSAO = rf"{_NUMERO}(?:{_UNIDADE})?(?:\s*[-–—−]\s*{_NUMERO}(?:{_UNIDADE})?)?"
# A unidade final é obrigatória; uma dimensão pode ser uma faixa inteira, com ou sem unidades repetidas.
MEDIDA = re.compile(rf"(?<![\w.\-–—−/]){_DIMENSAO}(?:\s*[x×]\s*{_DIMENSAO})*{_UNIDADE}\b", re.I)
NODE_COLUMNS = ["case_id", "node_id", "type", "label", "attributes"]
EDGE_COLUMNS = ["case_id", "edge_id", "source_id", "target_id", "relation", "attributes"]


def normalizar_rotulo(texto: str) -> tuple[str, list[str]]:
    texto = unicodedata.normalize("NFKC", texto)
    medidas = [m.group().strip() for m in MEDIDA.finditer(texto)]
    label = re.sub(r"\s+", " ", MEDIDA.sub(" ", texto)).strip(" \t\n.,;:()[]{}\"'").casefold()
    # Uma menção composta só de medida continua identificável.
    return label or texto.strip().casefold(), medidas


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _confianca(linha):
    valor = linha.get("confianca", "")
    if valor in (None, ""):
        return None
    valor = float(valor)
    if not math.isfinite(valor) or not 0 <= valor <= 1:
        raise ValueError("confianca deve estar entre 0 e 1")
    return valor


def montar_caso(case_id: str, texto: str, mencoes: list[dict], relacoes: list[dict],
                metadados: dict | None = None) -> tuple[list[dict], list[dict]]:
    """Mescla só mesmo tipo/polaridade; códigos conflitantes nunca são unidos por rótulo."""
    metadados = metadados or {}
    ids, preparadas, por_rotulo = set(), [], defaultdict(set)
    for m in mencoes:
        if m.get("case_id", case_id) != case_id or not m.get("id") or m["id"] in ids or m["id"] == "P1":
            raise ValueError(f"Identificador de menção inválido/duplicado: {m.get('id')}")
        ids.add(m["id"])
        if m.get("tipo") not in TIPOS or m.get("polaridade") not in {"present", "absent", "uncertain"}:
            raise ValueError(f"Tipo/polaridade inválidos: {m['id']}")
        i, f = int(m["start"]), int(m["end"])
        if not 0 <= i < f <= len(texto) or texto[i:f] != m["texto"]:
            raise ValueError(f"Span não corresponde ao texto: {case_id}/{m['id']}")
        _confianca(m)
        label, medidas = normalizar_rotulo(m.get("label") or m["texto"])
        polaridade, mesh = m.get("polaridade", "present"), m.get("mesh", "").strip()
        item = {**m, "start": i, "end": f, "label": label, "medidas": medidas,
                "polaridade": polaridade, "mesh": mesh}
        preparadas.append(item)
        if mesh:
            por_rotulo[(m["tipo"], polaridade, label)].add(mesh)
    grupos = defaultdict(list)
    for m in sorted(preparadas, key=lambda x: (x["start"], x["end"], x["id"])):
        chave_rotulo = (m["tipo"], m["polaridade"], m["label"])
        possiveis = por_rotulo[chave_rotulo]
        mesh = m["mesh"] or (next(iter(possiveis)) if len(possiveis) == 1 else "")
        chave = (m["tipo"], m["polaridade"], "mesh", mesh) if mesh else (*chave_rotulo, "rotulo")
        grupos[chave].append(m)
    paciente = {k: metadados[k] for k in ("age", "gender", "article_id") if metadados.get(k) not in (None, "")}
    nodes = [{"node_id": "P1", "type": "Patient", "label": f"case {case_id}", "attributes": paciente}]
    contadores, mapa = defaultdict(int), {}
    for grupo in grupos.values():
        primeiro = grupo[0]
        tipo = primeiro["tipo"]
        contadores[tipo] += 1
        node_id = NODE_PREFIXES[tipo] + str(contadores[tipo])
        for m in grupo:
            mapa[m["id"]] = node_id
        atributos = {"polarity": primeiro["polaridade"], "mentions": "|".join(m["id"] for m in grupo),
                     "mention_texts": _json([m["texto"] for m in grupo]),
                     "spans": _json([[m["start"], m["end"]] for m in grupo]),
                     "char_start": primeiro["start"], "char_end": primeiro["end"],
                     "evidence_text": primeiro["texto"]}
        medidas = list(dict.fromkeys(s for m in grupo for s in m["medidas"]))
        if medidas:
            atributos["size"] = "|".join(medidas)
        meshes = {m["mesh"] for m in grupo if m["mesh"]}
        if meshes:
            atributos["mesh"] = next(iter(meshes))
        confiancas = [c for m in grupo if (c := _confianca(m)) is not None]
        if confiancas:
            atributos["confianca"] = max(confiancas)
        fontes_polaridade = {m["fonte_polaridade"] for m in grupo if m.get("fonte_polaridade")}
        if fontes_polaridade:
            atributos["fonte_polaridade"] = "|".join(sorted(fontes_polaridade))
        nodes.append({"node_id": node_id, "type": tipo, "label": primeiro["label"], "attributes": atributos})
    tipos = {n["node_id"]: n["type"] for n in nodes}
    mapa["P1"] = "P1"
    spans = {m["id"]: (m["start"], m["end"]) for m in preparadas}
    arestas = {}
    for r in relacoes:
        if r.get("case_id", case_id) != case_id:
            raise ValueError("Relação de outro caso")
        nome = r["relacao"]
        if nome == "NONE":
            continue
        if nome not in DOMINIO:
            raise ValueError(f"Relação desconhecida: {nome}")
        if r["origem"] not in mapa or r["destino"] not in mapa:
            raise ValueError(f"Relação aponta para menção inexistente: {r}")
        a, b = mapa[r["origem"]], mapa[r["destino"]]
        origens, destinos = DOMINIO[nome]
        if tipos[a] not in origens or tipos[b] not in destinos:
            raise ValueError(f"Domínio inválido: {tipos[a]} -{nome}-> {tipos[b]}")
        confianca = _confianca(r)
        chave = (a, b, nome)
        atributos = arestas.setdefault(chave, {"mention_pairs": [], "fontes": set(), "evidence_spans": []})
        atributos["mention_pairs"].append([r["origem"], r["destino"]])
        limites = [spans[mid] for mid in (r["origem"], r["destino"]) if mid != "P1"]
        inicio, fim = min(i for i, _ in limites), max(f for _, f in limites)
        atributos["evidence_spans"].append([inicio, fim])
        if "char_start" not in atributos:
            atributos.update(char_start=inicio, char_end=fim, evidence_text=texto[inicio:fim])
        if r.get("fonte"):
            atributos["fontes"].add(r["fonte"])
        if confianca is not None:
            atributos["confianca"] = max(atributos.get("confianca", 0), confianca)
    edges = []
    for (a, b, nome), attrs in arestas.items():
        attrs["mention_pairs"] = _json(attrs["mention_pairs"])
        attrs["evidence_spans"] = _json(attrs["evidence_spans"])
        attrs["fonte"] = "|".join(sorted(attrs.pop("fontes")))
        edges.append({"source_id": a, "target_id": b, "relation": nome, "attributes": attrs})
    conceitos = {}
    for node in list(nodes):
        mesh = node["attributes"].get("mesh")
        if not mesh:
            continue
        if mesh not in conceitos:
            conceitos[mesh] = "C" + str(len(conceitos) + 1)
            nodes.append({"node_id": conceitos[mesh], "type": "Concept", "label": mesh,
                          "attributes": {"code": mesh, "vocabulary": "AnatomicalSite" if mesh.startswith("ANAT") else "MeSH"}})
        edges.append({"source_id": node["node_id"], "target_id": conceitos[mesh], "relation": "SAME_AS", "attributes": {}})
    return ([{"case_id": case_id, **n} for n in nodes],
            [{"case_id": case_id, "edge_id": f"e{i}", **e} for i, e in enumerate(edges, 1)])


def _ler_tabela(caminho, obrigatorias):
    with Path(caminho).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not set(obrigatorias) <= set(reader.fieldnames or []):
            raise ValueError(f"{caminho}: precisa das colunas {obrigatorias}")
        return list(reader)


def montar(mencoes: Path, relacoes: Path, corpus: Path = CASOS_PADRAO,
           saida: Path = REPO / "project2/data/grafo", case_id: str | None = None,
           gold: Path | None = None, visualizador: Path | None = None,
           polaridade_regras: bool = False, ignorar_sem_tipo: bool = False,
           p1_grafos: Path | None = REPO / "project1/data/processed") -> dict:
    por_mencao, por_relacao = defaultdict(list), defaultdict(list)
    colunas = ["case_id", "id", "start", "end", "texto", "tipo", "mesh"]
    if not polaridade_regras:
        colunas.append("polaridade")
    for m in _ler_tabela(mencoes, colunas):
        por_mencao[m["case_id"]].append(m)
    for r in _ler_tabela(relacoes, ["case_id", "origem", "destino", "relacao"]):
        por_relacao[r["case_id"]].append(r)
    if case_id and gold:
        raise ValueError("Use --case-id ou --gold, não ambos")
    selecionados = {case_id} if case_id else casos_gold(gold) if gold else set(por_mencao) | set(por_relacao)
    if not selecionados:
        raise ValueError("Sem casos para montar; use --case-id ou --gold para incluir casos sem menções")
    if any(re.fullmatch(r"PMC\d+_\d+", c) is None for c in selecionados):
        raise ValueError("case_id inválido")
    casos = {r["case_id"]: r for r in iter_registros(corpus) if r["case_id"] in selecionados}
    if selecionados - casos.keys():
        raise ValueError(f"Casos ausentes no corpus: {sorted(selecionados - casos.keys())}")
    omitidas, relacoes_omitidas, completadas = 0, 0, 0
    for c in sorted(casos):
        texto = casos[c]["case_text"]
        frases = dividir_frases(texto) if polaridade_regras else []
        ids, sem_tipo = set(), set()
        for m in por_mencao[c]:
            if not m["id"] or m["id"] == "P1" or m["id"] in ids:
                raise ValueError(f"ID inválido/duplicado: {c}/{m['id']}")
            ids.add(m["id"])
            i, f = int(m["start"]), int(m["end"])
            if not 0 <= i < f <= len(texto) or texto[i:f] != m["texto"]:
                raise ValueError(f"Span inválido: {c}/{m['id']}")
            if not m["tipo"]:
                if not ignorar_sem_tipo:
                    raise ValueError("Há menções sem tipo. Use --ignorar-sem-tipo para omiti-las com contagem no resumo.")
                sem_tipo.add(m["id"])
            if polaridade_regras and not m.get("polaridade"):
                frase = next((s for s in frases if s.start <= i and f <= s.end), None)
                if frase is None:
                    raise ValueError(f"Menção atravessa limite de frase: {c}/{m['id']}")
                m["polaridade"] = detect_polarity(frase.text)
                m["fonte_polaridade"] = "regra_p1_sentenca"
                completadas += 1
        por_mencao[c] = [m for m in por_mencao[c] if m["id"] not in sem_tipo]
        mantidas = []
        for r in por_relacao[c]:
            if r["origem"] not in ids | {"P1"} or r["destino"] not in ids | {"P1"}:
                raise ValueError(f"Relação aponta para menção inexistente: {r}")
            if r["origem"] in sem_tipo or r["destino"] in sem_tipo:
                relacoes_omitidas += 1
            else:
                mantidas.append(r)
        por_relacao[c] = mantidas
        omitidas += len(sem_tipo)
    # Valida todos os grafos antes de gravar saídas.
    grafos = {c: montar_caso(c, casos[c]["case_text"], por_mencao[c], por_relacao[c], casos[c]) for c in sorted(casos)}
    saida = Path(saida)
    saida.mkdir(parents=True, exist_ok=True)
    for c, (nodes, edges) in grafos.items():
        for sufixo, colunas, linhas in (("nodes", NODE_COLUMNS, nodes), ("edges", EDGE_COLUMNS, edges)):
            with (saida / f"{c}-{sufixo}.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=colunas)
                writer.writeheader()
                writer.writerows({**l, "attributes": serialize_attributes(l["attributes"])} for l in linhas)
    if visualizador:
        site = Path(visualizador)
        site.mkdir(parents=True, exist_ok=True)
        fonte = REPO / "project1/visualizer"
        for nome in ("index.html", "app.js", "style.css"):
            shutil.copy2(fonte / nome, site / nome)
        shutil.copytree(fonte / "vendor", site / "vendor", dirs_exist_ok=True)
        dados = site / "data"
        dados.mkdir(exist_ok=True)
        p1_dir = Path(p1_grafos) if p1_grafos else None
        p1_disponivel = p1_dir is not None and p1_dir.is_dir()
        manifest_cases = []
        for c, (nodes, edges) in grafos.items():
            grafo_p2 = {"nodes": [{k: v for k, v in n.items() if k != "case_id"} for n in nodes],
                        "edges": [{k: v for k, v in e.items() if k != "case_id"} for e in edges]}
            graphs_dict = {
                "projeto2": grafo_p2,
                "combinado": grafo_p2,  # Mantém compatibilidade com testes e visualizador legado
            }
            available_graphs = ["projeto2"]
            if p1_disponivel:
                p1_nodes_csv = p1_dir / f"{c}-nodes.csv"
                p1_edges_csv = p1_dir / f"{c}-edges.csv"
                if p1_nodes_csv.is_file() and p1_edges_csv.is_file():
                    graphs_dict["projeto1"] = {
                        "nodes": read_nodes_csv(p1_nodes_csv),
                        "edges": read_edges_csv(p1_edges_csv),
                    }
                    available_graphs.insert(0, "projeto1")
            payload = {"case_id": c, "case_text": casos[c]["case_text"], "graphs": graphs_dict}
            (dados / f"{c}.json").write_text(_json(payload), encoding="utf-8")
            manifest_cases.append({"case_id": c, "graphs": available_graphs})
        (dados / "manifest.json").write_text(_json({"cases": manifest_cases}), encoding="utf-8")
    resumo = {"casos": len(grafos), "nos": sum(len(n) for n, _ in grafos.values()),
              "arestas": sum(len(e) for _, e in grafos.values()), "saida": str(saida),
              "mencoes_sem_tipo_omitidas": omitidas, "relacoes_com_ponta_sem_tipo_omitidas": relacoes_omitidas,
              "polaridades_completadas_por_regra_p1": completadas}
    (saida / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return resumo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mencoes", type=Path, default=REPO / "project2/data/mencoes_tipadas.csv")
    parser.add_argument("--relacoes", type=Path, default=REPO / "project2/data/relacoes.csv")
    parser.add_argument("--corpus", type=Path, default=CASOS_PADRAO)
    parser.add_argument("--saida", type=Path, default=REPO / "project2/data/grafo")
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--case-id")
    grupo.add_argument("--gold", type=Path)
    parser.add_argument("--visualizador", type=Path, help="copia o visualizador P1 e exporta JSON neste diretório")
    parser.add_argument("--p1-grafos", type=Path, default=REPO / "project1/data/processed",
                        help="diretório com os grafos processados do P1 para inclusão no visualizador (default: project1/data/processed)")
    parser.add_argument("--polaridade-regras", action="store_true", help="completa polaridades ausentes com a regra de sentença do P1")
    parser.add_argument("--ignorar-sem-tipo", action="store_true", help="omite menções não classificadas e suas relações; registra a contagem")
    try:
        print(json.dumps(montar(**vars(parser.parse_args())), ensure_ascii=False, indent=2))
    except (ValueError, FileNotFoundError) as error:
        parser.exit(2, f"Erro: {error}\n")


if __name__ == "__main__":
    main()
