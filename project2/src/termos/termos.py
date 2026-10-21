"""N-gramas, PMI de pares adjacentes e C-value, com contagem incremental em SQLite."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sqlite3
import sys
import tempfile
import time
import unicodedata
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from project2.src.comum import CASOS_PADRAO, GOLD_PADRAO, REPO, casos_gold, dividir_frases, etiquetar, iter_casos, tokenizar

COLUNAS = ["termo", "n", "frequencia", "pmi", "c_value"]
PALAVRA = re.compile(r"[^\W\d_][\w]*(?:[-/][\w]+)*", re.UNICODE)
TERMOS_PADRAO = REPO / "project2/data/termos.csv"
GAZETTEER = REPO / "project1/src/dicionarios/gazetteer/mesh_gazetteer.csv"


def normalizar(texto: str) -> str:
    """Chave lexical conservadora; números, unidades e pontuação distinguem conceitos."""
    return " ".join(unicodedata.normalize("NFKC", texto).casefold().split())


def _forma(tags) -> bool:
    return tags[-1] == "NOUN" and all(t in ("ADJ", "NOUN") for t in tags)


def contar_caso(texto: str, n_max: int = 4) -> tuple[Counter, Counter, Counter, Counter]:
    """Contagens total/POS-válida e marginais esquerda/direita de bigramas."""
    contagens, validas, esquerda, direita = (Counter() for _ in range(4))
    tokens = tokenizar(texto)
    tags = etiquetar(tokens)
    indice = 0
    for frase in dividir_frases(texto):
        while indice < len(tokens) and tokens[indice].start < frase.start:
            indice += 1
        janela = []
        while indice < len(tokens) and tokens[indice].start < frase.end:
            t, tag = tokens[indice], tags[indice]
            # Pontuação e unidades interrompem a sequência: não formamos 'pain fever' de 'pain, fever'.
            janela.append((t.text.lower(), tag) if t.kind == "WORD" and PALAVRA.fullmatch(t.text) else None)
            indice += 1
        for i, item in enumerate(janela):
            if item is None:
                continue
            palavras, classes = [], []
            for n in range(1, n_max + 1):
                if i + n > len(janela) or janela[i + n - 1] is None:
                    break
                palavra, tag = janela[i + n - 1]
                palavras.append(palavra)
                classes.append(tag)
                chave = " ".join(palavras)
                contagens[(chave, n)] += 1
                if _forma(classes):
                    validas[chave] += 1
                if n == 2:
                    esquerda[palavras[0]] += 1
                    direita[palavras[1]] += 1
    return contagens, validas, esquerda, direita


def calcular_c_values(candidatos: dict[tuple[str, ...], int]) -> dict[tuple[str, ...], float]:
    """Índice dos subtermos contíguos: O(candidatos * n_max²), sem comparar todos os pares."""
    somas, quantidades = Counter(), Counter()
    for maior, frequencia in candidatos.items():
        menores = {maior[i:i + n] for n in range(2, len(maior)) for i in range(len(maior) - n + 1)}
        for menor in menores:
            if menor in candidatos:
                somas[menor] += frequencia
                quantidades[menor] += 1
    return {a: math.log2(len(a)) * (f - somas[a] / quantidades[a] if quantidades[a] else f)
            for a, f in candidatos.items()}


def _sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as handle:
        for bloco in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


def _referencia(caminho: Path) -> str:
    try:
        return caminho.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(caminho)


def gerar(saida: Path | str = TERMOS_PADRAO, freq_min: int = 2, n_max: int = 4,
          *, corpus: Path | str = CASOS_PADRAO, gold: Path | str = GOLD_PADRAO,
          limite: int | None = None, banco: Path | str | None = None) -> dict:
    if freq_min < 1 or n_max not in (2, 3, 4):
        raise ValueError("freq_min deve ser >= 1 e n_max deve estar entre 2 e 4")
    excluidos = casos_gold(gold)  # antes de criar arquivos ou ler o corpus
    corpus, saida, gold = Path(corpus), Path(saida), Path(gold)
    inicio = time.perf_counter()
    processados, ignorados, pares = 0, 0, 0
    with tempfile.TemporaryDirectory(prefix="pnl-termos-") as temporario:
        db_path = Path(banco) if banco else Path(temporario) / "contagens.sqlite3"
        if banco:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            db_path.touch(exist_ok=False)  # nunca apaga um banco de uma execução anterior
        from contextlib import closing
        with closing(sqlite3.connect(db_path)) as db:
            with db:
                db.execute("CREATE TABLE ngramas (termo TEXT PRIMARY KEY, n INTEGER, frequencia INTEGER, validas INTEGER)")
                db.execute("CREATE TABLE marginais (palavra TEXT PRIMARY KEY, esquerda INTEGER, direita INTEGER)")
                for case_id, texto in iter_casos(corpus, limite):
                    if case_id in excluidos:
                        ignorados += 1
                        continue
                    contagens, validas, esq, dire = contar_caso(texto, n_max)
                    db.executemany("INSERT INTO ngramas VALUES (?,?,?,?) ON CONFLICT(termo) DO UPDATE SET "
                                   "frequencia=frequencia+excluded.frequencia, validas=validas+excluded.validas",
                                   ((t, n, f, validas[t]) for (t, n), f in contagens.items()))
                    db.executemany("INSERT INTO marginais VALUES (?,?,?) ON CONFLICT(palavra) DO UPDATE SET "
                                   "esquerda=esquerda+excluded.esquerda, direita=direita+excluded.direita",
                                   ((p, esq[p], dire[p]) for p in esq.keys() | dire.keys()))
                    pares += sum(esq.values())
                    processados += 1
                    if processados % 100 == 0:
                        db.commit()
                        print(f"{processados} casos processados; {time.perf_counter() - inicio:.1f}s", file=sys.stderr, flush=True)
                db.commit()
                if not processados:
                    raise ValueError("Nenhum caso de treino após excluir o gabarito")
                candidatos = {tuple(t.split()): f for t, f in db.execute(
                    "SELECT termo, frequencia FROM ngramas WHERE n >= 2 AND frequencia >= ? AND validas * 2 >= frequencia",
                    (freq_min,))}
                c_values = calcular_c_values(candidatos)

                @lru_cache(maxsize=8192)
                def pmi_par(a, b):
                    f = db.execute("SELECT frequencia FROM ngramas WHERE termo=?", (a + " " + b,)).fetchone()[0]
                    esquerda = db.execute("SELECT esquerda FROM marginais WHERE palavra=?", (a,)).fetchone()[0]
                    direita = db.execute("SELECT direita FROM marginais WHERE palavra=?", (b,)).fetchone()[0]
                    return math.log2(f * pares / (esquerda * direita))

                linhas = [{"termo": " ".join(a), "n": len(a), "frequencia": f,
                           "pmi": round(min(pmi_par(x, y) for x, y in zip(a, a[1:])), 6),
                           "c_value": round(c_values[a], 6)} for a, f in candidatos.items()]
                linhas.sort(key=lambda r: (-r["c_value"], -r["pmi"], -r["frequencia"], r["termo"]))
                totais = {str(n): f for n, f in db.execute("SELECT n, SUM(frequencia) FROM ngramas GROUP BY n")}
    saida.parent.mkdir(parents=True, exist_ok=True)
    with saida.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUNAS)
        writer.writeheader()
        writer.writerows(linhas)
    resumo = {"corpus": _referencia(corpus), "corpus_sha256": _sha256(corpus), "gold": _referencia(gold),
              "gold_sha256": _sha256(gold), "lista_gold": sorted(excluidos),
              "casos_processados": processados, "casos_gold_excluidos": ignorados,
              "limite": limite, "freq_min": freq_min, "n_max": n_max, "ocorrencias_por_n": totais,
              "termos": len(linhas), "tempo_s": round(time.perf_counter() - inicio, 3),
              "codigo_sha256": _sha256(Path(__file__)),
              "tokenizador_sha256": _sha256(REPO / "project1/src/tokenizacao/tokenizers.py"),
              "comum_texto_sha256": _sha256(REPO / "project2/src/comum/texto.py"),
              "comum_corpus_sha256": _sha256(REPO / "project2/src/comum/corpus.py"),
              "pos_bio_sha256": _sha256(REPO / "project1/src/sintagmas/pos_bio.py"),
              "hmm_sha256": _sha256(REPO / "project1/src/sintagmas/model/hmm_pos.json"),
              "pmi": "minimo do PMI dos pares adjacentes; marginais posicionais no universo de bigramas",
              "filtro_pos": "ao menos metade das ocorrencias com (ADJ|NOUN)* NOUN"}
    saida.with_suffix(".json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return resumo


def ler_termos(caminho: Path | str = TERMOS_PADRAO, limite: int | None = None) -> list[tuple[str, ...]]:
    if limite is not None and limite < 0:
        raise ValueError("limite deve ser >= 0")
    with Path(caminho).open(encoding="utf-8", newline="") as handle:
        leitor = csv.DictReader(handle)
        if not set(COLUNAS) <= set(leitor.fieldnames or []):
            raise ValueError(f"Tabela de termos precisa de {COLUNAS}")
        from itertools import islice
        return [tuple(linha["termo"].split()) for linha in islice(leitor, limite)]


def comparar(termos: Path | str = TERMOS_PADRAO, gazetteer: Path | str = GAZETTEER,
             saida: Path | str = REPO / "project2/data/resultados/termos.csv", top: int = 100) -> dict:
    """Cobertura lexical exata normalizada; termos desconhecidos são candidatos, não acertos clínicos."""
    if top < 1:
        raise ValueError("top deve ser >= 1")
    codigos = defaultdict(set)
    with Path(gazetteer).open(encoding="utf-8-sig", newline="") as handle:
        for linha in csv.DictReader(handle):
            codigos[normalizar(linha["term"])].add(linha["code"])
    with Path(termos).open(encoding="utf-8", newline="") as handle:
        from itertools import islice
        ranking = list(islice(csv.DictReader(handle), top))
    linhas = [{"posicao": i, **linha, "conhecido_mesh": int(normalizar(linha["termo"]) in codigos),
               "codigos_mesh": "|".join(sorted(codigos.get(normalizar(linha["termo"]), ())))}
              for i, linha in enumerate(ranking, 1)]
    saida = Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    with saida.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["posicao", *COLUNAS, "conhecido_mesh", "codigos_mesh"])
        writer.writeheader()
        writer.writerows(linhas)
    conhecidos = sum(l["conhecido_mesh"] for l in linhas)
    resumo = {"top_solicitado": top, "avaliados": len(linhas), "conhecidos_mesh": conhecidos,
              "candidatos_novos": len(linhas) - conhecidos,
              "cobertura_lexical": conhecidos / len(linhas) if linhas else 0.0,
              "termos_sha256": _sha256(Path(termos)), "gazetteer_sha256": _sha256(Path(gazetteer)),
              "codigo_sha256": _sha256(Path(__file__)),
              "normalizacao": "NFKC, casefold e compactacao de espacos; preserva numeros, unidades e pontuacao",
              "interpretacao": "cobertura lexical; nao mede precisao, recall ou F1 de entidades"}
    saida.with_suffix(".json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return resumo


ASSOCIACOES_PADRAO = REPO / "project2/data/associacoes.csv"
COLUNAS_ASSOCIACOES = ["codigo_a", "termo_a", "codigo_b", "termo_b", "casos_ab", "casos_a", "casos_b", "pmi"]


def _silver_padrao() -> Path:
    preferido = REPO / "project2/data/silver/mencoes.csv"
    return preferido if preferido.is_file() else REPO / "project2/data/silver/entidades_tipadas.csv"


def associar(silver: Path | str | None = None, gazetteer: Path | str = GAZETTEER,
             gold: Path | str = GOLD_PADRAO, saida: Path | str = ASSOCIACOES_PADRAO,
             grafo_prefixo: Path | str = REPO / "project2/data/resultados/associacoes",
             freq_min: int = 2, top_grafo: int = 30) -> dict:
    """PMI entre pares de conceitos MeSH que coocorrem no mesmo caso do silver (excluindo o gold)."""
    if freq_min < 1 or top_grafo < 1:
        raise ValueError("freq_min e top_grafo devem ser >= 1")
    excluidos = casos_gold(gold)
    silver_path = Path(silver) if silver else _silver_padrao()
    gazetteer, gold, saida = Path(gazetteer), Path(gold), Path(saida)
    if not silver_path.is_file():
        raise FileNotFoundError(f"Silver não encontrado: {silver_path}")

    nomes_mesh: dict[str, str] = {}
    if gazetteer.is_file():
        with gazetteer.open(encoding="utf-8-sig", newline="") as handle:
            for linha in csv.DictReader(handle):
                code = (linha.get("code") or "").strip()
                pref = (linha.get("preferred_term") or linha.get("term") or "").strip()
                if code and pref and code not in nomes_mesh:
                    nomes_mesh[code] = pref

    casos_vistos: set[str] = set()
    casos_excluidos: set[str] = set()
    conceitos_por_caso: dict[str, set[str]] = defaultdict(set)
    rotulos_fallback: dict[str, Counter] = defaultdict(Counter)

    with silver_path.open(encoding="utf-8-sig", newline="") as handle:
        for linha in csv.DictReader(handle):
            cid = (linha.get("case_id") or "").strip()
            if not cid:
                continue
            if cid in excluidos:
                casos_excluidos.add(cid)
                continue
            casos_vistos.add(cid)
            pol = (linha.get("polaridade") or linha.get("polarity") or "present").strip().lower()
            if pol == "absent":
                continue
            codigo = (linha.get("mesh") or linha.get("concept_code") or "").strip()
            if not codigo or codigo.lower() == "nan" or not codigo.startswith("D"):
                continue
            conceitos_por_caso[cid].add(codigo)
            texto = (linha.get("texto") or "").strip()
            if texto:
                rotulos_fallback[codigo][texto.lower()] += 1

    total_casos = len(casos_vistos)
    if total_casos == 0:
        raise ValueError("Nenhum caso elegível no silver após excluir o gabarito")

    contagem_conceito: Counter = Counter()
    contagem_pares: Counter = Counter()
    for codigos in conceitos_por_caso.values():
        ordenados = sorted(codigos)
        for c in ordenados:
            contagem_conceito[c] += 1
        for i, a in enumerate(ordenados):
            for b in ordenados[i + 1:]:
                contagem_pares[(a, b)] += 1

    def nome_conceito(codigo: str) -> str:
        if codigo in nomes_mesh:
            return nomes_mesh[codigo]
        if rotulos_fallback[codigo]:
            return rotulos_fallback[codigo].most_common(1)[0][0]
        return codigo

    linhas = []
    for (a, b), c_ab in contagem_pares.items():
        if c_ab < freq_min:
            continue
        c_a, c_b = contagem_conceito[a], contagem_conceito[b]
        pmi = math.log2((c_ab * total_casos) / (c_a * c_b))
        linhas.append({
            "codigo_a": a,
            "termo_a": nome_conceito(a),
            "codigo_b": b,
            "termo_b": nome_conceito(b),
            "casos_ab": c_ab,
            "casos_a": c_a,
            "casos_b": c_b,
            "pmi": round(pmi, 6),
        })
    linhas.sort(key=lambda r: (-r["pmi"], -r["casos_ab"], r["codigo_a"], r["codigo_b"]))

    saida.parent.mkdir(parents=True, exist_ok=True)
    with saida.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUNAS_ASSOCIACOES)
        writer.writeheader()
        writer.writerows(linhas)

    # Exporta as associações mais fortes como um grafo de conceitos (nodes + edges)
    prefixo = Path(grafo_prefixo)
    prefixo.parent.mkdir(parents=True, exist_ok=True)
    nodes_path = prefixo.with_name(prefixo.name + "-nodes.csv")
    edges_path = prefixo.with_name(prefixo.name + "-edges.csv")
    top_linhas = linhas[:top_grafo]
    nos_vistos: dict[str, dict] = {}
    arestas_grafo: list[dict] = []
    for idx, r in enumerate(top_linhas, 1):
        for col_c, col_t, col_n in (("codigo_a", "termo_a", "casos_a"), ("codigo_b", "termo_b", "casos_b")):
            cod = r[col_c]
            if cod not in nos_vistos:
                nos_vistos[cod] = {
                    "node_id": cod,
                    "type": "Concept",
                    "label": r[col_t],
                    "attributes": f"code={cod}; cases={r[col_n]}",
                }
        arestas_grafo.append({
            "edge_id": f"a{idx}",
            "source_id": r["codigo_a"],
            "target_id": r["codigo_b"],
            "relation": "ASSOCIATED_WITH",
            "attributes": f"cases_cooccur={r['casos_ab']}; pmi={r['pmi']}",
        })
    with nodes_path.open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=["node_id", "type", "label", "attributes"])
        w.writeheader()
        w.writerows(nos_vistos.values())
    with edges_path.open("w", encoding="utf-8", newline="") as handle:
        w = csv.DictWriter(handle, fieldnames=["edge_id", "source_id", "target_id", "relation", "attributes"])
        w.writeheader()
        w.writerows(arestas_grafo)

    resumo = {
        "silver": _referencia(silver_path),
        "silver_sha256": _sha256(silver_path),
        "gold": _referencia(gold),
        "gold_sha256": _sha256(gold),
        "casos_processados": total_casos,
        "casos_gold_excluidos": len(casos_excluidos),
        "conceitos_distintos": len(contagem_conceito),
        "freq_min": freq_min,
        "pares_associados": len(linhas),
        "grafo_nos": len(nos_vistos),
        "grafo_arestas": len(arestas_grafo),
        "grafo_nodes_csv": _referencia(nodes_path),
        "grafo_edges_csv": _referencia(edges_path),
    }
    saida.with_suffix(".json").write_text(json.dumps(resumo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return resumo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="comando", required=True)
    p = sub.add_parser("gerar")
    p.add_argument("--corpus", type=Path, default=CASOS_PADRAO)
    p.add_argument("--gold", type=Path, default=GOLD_PADRAO)
    p.add_argument("--saida", type=Path, default=TERMOS_PADRAO)
    p.add_argument("--freq-min", type=int, default=2)
    p.add_argument("--n-max", type=int, choices=(2, 3, 4), default=4)
    p.add_argument("--limite", type=int)
    p.add_argument("--banco", type=Path, help="preserva contagens em um banco novo; deve caber em disco")
    p = sub.add_parser("comparar")
    p.add_argument("--termos", type=Path, default=TERMOS_PADRAO)
    p.add_argument("--gazetteer", type=Path, default=GAZETTEER)
    p.add_argument("--saida", type=Path, default=REPO / "project2/data/resultados/termos.csv")
    p.add_argument("--top", type=int, default=100)
    p = sub.add_parser("associar")
    p.add_argument("--silver", type=Path, default=None)
    p.add_argument("--gazetteer", type=Path, default=GAZETTEER)
    p.add_argument("--gold", type=Path, default=GOLD_PADRAO)
    p.add_argument("--saida", type=Path, default=ASSOCIACOES_PADRAO)
    p.add_argument("--grafo-prefixo", type=Path, default=REPO / "project2/data/resultados/associacoes")
    p.add_argument("--freq-min", type=int, default=2)
    p.add_argument("--top-grafo", type=int, default=30)
    args = vars(parser.parse_args())
    comando = args.pop("comando")
    acoes = {"gerar": gerar, "comparar": comparar, "associar": associar}
    try:
        print(json.dumps(acoes[comando](**args), ensure_ascii=False, indent=2))
    except (ValueError, FileNotFoundError, RuntimeError) as error:
        parser.exit(2, f"Erro: {error}\n")


if __name__ == "__main__":
    main()

