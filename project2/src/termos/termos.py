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
        with sqlite3.connect(db_path) as db:
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
    args = vars(parser.parse_args())
    comando = args.pop("comando")
    try:
        print(json.dumps((gerar if comando == "gerar" else comparar)(**args), ensure_ascii=False, indent=2))
    except (ValueError, FileNotFoundError, RuntimeError) as error:
        parser.exit(2, f"Erro: {error}\n")


if __name__ == "__main__":
    main()
