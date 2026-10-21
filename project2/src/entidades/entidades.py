"""Etapa 2 (#33): onde cada entidade começa e termina, com um CRF treinado no silver.

    python project2/src/entidades/entidades.py mock               # gera silver, linha de base e termos
    python project2/src/entidades/entidades.py treinar [--termos]
    python project2/src/entidades/entidades.py prever [--termos] [--todos]
    python project2/src/entidades/entidades.py comparar           # regras × pos_bio × CRF × CRF+termos

A marcação é BIO sem tipo: quem dá o tipo é a etapa 3. Cada palavra vira um dicionário de pistas
(a palavra, prefixos e sufixos, formato, classe gramatical do HMM, vizinhas a 2 posições e, com
--termos, se faz parte de um termo do termos.csv). O CRF aprende pesos para as pistas e para as
transições entre rótulos, e escolhe a sequência B/I/O mais provável da frase inteira.
"""
from __future__ import annotations

import argparse
import csv
import pickle
import time
import sys
from collections import defaultdict
from pathlib import Path

import sklearn_crfsuite

REPO = Path(__file__).resolve().parents[3]
PROJECT1_SRC = REPO / "project1" / "src"
for _pasta in (
    REPO,
    PROJECT1_SRC / "grafo_lote",
    PROJECT1_SRC,
    PROJECT1_SRC / "tokenizacao",
    PROJECT1_SRC / "sintagmas",
    PROJECT1_SRC / "dicionarios",
):
    if str(_pasta) not in sys.path:
        sys.path.insert(0, str(_pasta))

from project2.src.avaliacao import avaliar as avaliacao  # noqa: E402
from project2.src.comum import (  # noqa: E402
    casos_gold,
    dividir_frases,
    etiquetar,
    ler_casos,
    tokenizar,
)
from project2.src.dados import silver as dados_silver  # noqa: E402
from project2.src.termos import termos as termos_mod  # noqa: E402

DADOS = REPO / "project2" / "data"
SILVER = DADOS / "silver" / "mencoes.csv"
REGRAS = DADOS / "regras" / "mencoes.csv"
GOLD = DADOS / "gold" / "mencoes.csv"
TERMOS = DADOS / "termos.csv"
MENCOES = DADOS / "mencoes.csv"
RESULTADOS = DADOS / "resultados"
MODELOS = REPO / "project2" / "models" / "entidades"
GRADE = [(c1, c2) for c1 in (0.05, 0.1, 0.3) for c2 in (0.01, 0.05, 0.1)]


# ================================================================== spans e BIO ==
def ler_mencoes(caminho: Path) -> dict[str, list[tuple[int, int]]]:
    por_caso = defaultdict(list)
    with open(caminho, encoding="utf-8", newline="") as handle:
        for linha in csv.DictReader(handle):
            por_caso[linha["case_id"]].append((int(linha["start"]), int(linha["end"])))
    return por_caso


def achatar(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Sem sobreposição: em cada conflito fica o span mais longo (BIO plano não aninha)."""
    ficam = []
    for inicio, fim in sorted(set(spans), key=lambda s: (s[0] - s[1], s[0])):
        if not any(inicio < f and i < fim for i, f in ficam):
            ficam.append((inicio, fim))
    return sorted(ficam)


def rotular(tokens: list, spans: list[tuple[int, int]]) -> list[str]:
    """B/I/O por token: entra no span todo token que tem interseção com ele."""
    rotulos = ["O"] * len(tokens)
    for inicio, fim in achatar(spans):
        dentro = [k for k, t in enumerate(tokens) if t.start < fim and inicio < t.end]
        for posicao, k in enumerate(dentro):
            rotulos[k] = "B" if posicao == 0 else "I"
    return rotulos


def spans_de_bio(tokens: list, rotulos: list[str]) -> list[tuple[int, int]]:
    """Inverso de `rotular`; um I sem B antes abre um span novo."""
    spans, aberto = [], None
    for tok, rotulo in zip(tokens, rotulos):
        if rotulo == "B" or (rotulo == "I" and aberto is None):
            if aberto:
                spans.append(aberto)
            aberto = [tok.start, tok.end]
        elif rotulo == "I":
            aberto[1] = tok.end
        else:
            if aberto:
                spans.append(aberto)
            aberto = None
    if aberto:
        spans.append(aberto)
    return [tuple(s) for s in spans]


def marcar_termos(palavras: list[str], termos: set[tuple[str, ...]], n_max: int = 4) -> list[str]:
    """B/I/O de 'faz parte de um termo', pelo casamento mais longo da esquerda para a direita."""
    marcas, i = ["O"] * len(palavras), 0
    minusculas = [p.lower() for p in palavras]
    while i < len(palavras):
        for n in range(min(n_max, len(palavras) - i), 1, -1):
            if tuple(minusculas[i:i + n]) in termos:
                marcas[i:i + n] = ["B"] + ["I"] * (n - 1)
                i += n
                break
        else:
            i += 1
    return marcas


# ===================================================================== pistas ==
def _formato(palavra: str) -> str:
    """Xxxx, xx-dd, X.X: maiúsculas, minúsculas e dígitos colapsados em sequência."""
    classes = ["X" if c.isupper() else "x" if c.islower() else "d" if c.isdigit() else c for c in palavra]
    curto = [c for k, c in enumerate(classes) if k == 0 or c != classes[k - 1]]
    return "".join(curto)


def pistas_da_palavra(frase: list[dict], i: int) -> dict:
    tok = frase[i]
    palavra = tok["texto"]
    pistas = {
        "bias": 1.0,
        "palavra": palavra.lower(),
        "pre1": palavra[:1].lower(), "pre2": palavra[:2].lower(), "pre3": palavra[:3].lower(),
        "suf1": palavra[-1:].lower(), "suf2": palavra[-2:].lower(), "suf3": palavra[-3:].lower(),
        "maiuscula": palavra.isupper(),
        "titulo": palavra.istitle(),
        "digito": any(c.isdigit() for c in palavra),
        "hifen": "-" in palavra,
        "formato": _formato(palavra),
        "pos": tok["pos"],
    }
    if "termo" in tok:
        pistas["termo"] = tok["termo"]
    for d in (-2, -1, 1, 2):
        j = i + d
        if 0 <= j < len(frase):
            pistas[f"{d:+d}:palavra"] = frase[j]["texto"].lower()
            pistas[f"{d:+d}:pos"] = frase[j]["pos"]
            if "termo" in frase[j]:
                pistas[f"{d:+d}:termo"] = frase[j]["termo"]
        else:
            pistas[f"{d:+d}:fora"] = True
    return pistas


def frases_do_caso(texto: str, termos: set | None = None) -> list[list[dict]]:
    """Frases como listas de tokens com offsets, classe gramatical e (opcional) marca de termo."""
    tokens = tokenizar(texto)
    tags = etiquetar(tokens)
    frases = []
    for frase in dividir_frases(texto):
        dentro = [(t, tag) for t, tag in zip(tokens, tags) if frase.start <= t.start < frase.end]
        if not dentro:
            continue
        itens = [{"texto": t.text, "start": t.start, "end": t.end, "pos": tag} for t, tag in dentro]
        if termos is not None:
            for item, marca in zip(itens, marcar_termos([x["texto"] for x in itens], termos)):
                item["termo"] = marca
        frases.append(itens)
    return frases


class _Tok:
    __slots__ = ("start", "end")

    def __init__(self, item):
        self.start, self.end = item["start"], item["end"]


def montar(casos: list[tuple[str, str]], mencoes: dict, termos: set | None):
    X, y, desalinhados = [], [], 0
    for case_id, texto in casos:
        spans = mencoes.get(case_id, [])
        frases = frases_do_caso(texto, termos)
        limites = {(t["start"], "i") for f in frases for t in f} | {(t["end"], "f") for f in frases for t in f}
        desalinhados += sum((i, "i") not in limites or (f, "f") not in limites for i, f in spans)
        for frase in frases:
            X.append([pistas_da_palavra(frase, i) for i in range(len(frase))])
            y.append(rotular([_Tok(t) for t in frase], spans))
    return X, y, desalinhados


# ============================================================= treino e predição ==
def _termos(com_termos: bool) -> set | None:
    if not com_termos:
        return None
    if not TERMOS.is_file():
        raise FileNotFoundError(f"{TERMOS} não existe: rode `python project2/src/termos/termos.py gerar` antes")
    return set(termos_mod.ler_termos(TERMOS))


def _caminho_modelo(com_termos: bool) -> Path:
    return MODELOS / ("crf_termos.pkl" if com_termos else "crf.pkl")


def _f1_exato(crf, X, y) -> float:
    """F1 de spans (casamento exato) num conjunto já rotulado, frase a frase."""
    pred, gold = [], []
    for k, (xs, ys, ps) in enumerate(zip(X, y, crf.predict(X))):
        toks = [_Tok({"start": j, "end": j + 1}) for j in range(len(xs))]
        pred += [(str(k), *s) for s in spans_de_bio(toks, ps)]
        gold += [(str(k), *s) for s in spans_de_bio(toks, ys)]
    return avaliacao.avaliar_mencoes(pred, gold)["exato"]["f1"]


def casos_de_treino(casos: list[tuple[str, str]], mencoes: dict, gold: set[str]) -> list[tuple[str, str]]:
    """Casos com menções no silver, nunca os do gabarito."""
    return sorted((c, t) for c, t in casos if c in mencoes and c not in gold)


def treinar(com_termos: bool = False) -> dict:
    """Busca c1/c2 em 20% dos casos do silver, retreina em todos e salva o modelo."""
    mencoes = ler_mencoes(SILVER)
    casos = casos_de_treino(ler_casos(), mencoes, casos_gold())
    validacao = casos[::5]
    treino = [c for k, c in enumerate(casos) if k % 5]
    termos = _termos(com_termos)

    X_tr, y_tr, desalinhados = montar(treino, mencoes, termos)
    X_va, y_va, _ = montar(validacao, mencoes, termos)
    notas = []
    for c1, c2 in GRADE:
        crf = sklearn_crfsuite.CRF(algorithm="lbfgs", c1=c1, c2=c2, max_iterations=200,
                                   all_possible_transitions=True)
        crf.fit(X_tr, y_tr)
        notas.append((_f1_exato(crf, X_va, y_va), c1, c2))
    f1_val, c1, c2 = max(notas)

    inicio = time.perf_counter()
    crf = sklearn_crfsuite.CRF(algorithm="lbfgs", c1=c1, c2=c2, max_iterations=200,
                               all_possible_transitions=True)
    crf.fit(X_tr + X_va, y_tr + y_va)
    tempo = time.perf_counter() - inicio

    MODELOS.mkdir(parents=True, exist_ok=True)
    with open(_caminho_modelo(com_termos), "wb") as handle:
        pickle.dump(crf, handle)
    return {"modelo": str(_caminho_modelo(com_termos).relative_to(REPO)), "casos_treino": len(casos),
            "frases": len(X_tr) + len(X_va), "c1": c1, "c2": c2, "f1_validacao": round(f1_val, 4),
            "spans_desalinhados": desalinhados, "tempo_treino_s": round(tempo, 1)}


def prever(casos: list[tuple[str, str]], com_termos: bool = False) -> list[tuple[str, int, int]]:
    caminho = _caminho_modelo(com_termos)
    if not caminho.is_file():
        raise FileNotFoundError(f"{caminho} não existe: rode `treinar{' --termos' if com_termos else ''}` antes")
    with open(caminho, "rb") as handle:
        crf = pickle.load(handle)
    termos = _termos(com_termos)
    saida = []
    for case_id, texto in casos:
        frases = frases_do_caso(texto, termos)
        rotulos = crf.predict([[pistas_da_palavra(f, i) for i in range(len(f))] for f in frases])
        for frase, ys in zip(frases, rotulos):
            saida += [(case_id, *s) for s in spans_de_bio([_Tok(t) for t in frase], ys)]
    return saida


def gravar_mencoes(spans: list[tuple[str, int, int]], textos: dict[str, str], caminho: Path = MENCOES) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    contador = defaultdict(int)
    with open(caminho, "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["case_id", "id", "start", "end", "texto"])
        for case_id, inicio, fim in sorted(spans):
            contador[case_id] += 1
            writer.writerow([case_id, f"m{contador[case_id]}", inicio, fim, textos[case_id][inicio:fim]])


# ================================================================== comparação ==
def spans_pos_bio(casos: list[tuple[str, str]]) -> list[tuple[str, int, int]]:
    """Linha 'só pos_bio.py': spans da camada externa do BIO por sintagmas nominais do projeto 1."""
    import pos_bio

    tagger = pos_bio.HMMTagger()
    saida = []
    for case_id, texto in casos:
        _, _, spans, _ = pos_bio.process(texto, tagger)
        saida += [(case_id, sp.tokens[0].start, sp.tokens[-1].end) for sp in spans if sp.layer == 0]
    return saida


def _plano(spans: list[tuple[str, int, int]]) -> list[tuple[str, int, int]]:
    por_caso = defaultdict(list)
    for case_id, inicio, fim in spans:
        por_caso[case_id].append((inicio, fim))
    return [(c, *s) for c, lista in por_caso.items() for s in achatar(lista)]


def comparar() -> list[dict]:
    """As 4 linhas da #33, nos dois casamentos, sobre os casos do gabarito."""
    gold_ids = casos_gold()
    casos = [(c, t) for c, t in ler_casos() if c in gold_ids]
    textos = dict(casos)
    gold = [(c, *s) for c, lista in ler_mencoes(GOLD).items() for s in lista]
    regras = [(c, *s) for c, lista in ler_mencoes(REGRAS).items() if c in gold_ids for s in lista]

    treinos = {com: treinar(com) for com in (False, True)}
    sistemas = {
        "regras P1": _plano(regras),
        "só pos_bio": _plano(spans_pos_bio(casos)),
        "CRF": prever(casos, False),
        "CRF + termos": prever(casos, True),
    }
    # mencoes.csv sai da variante que foi melhor na validação do silver, nunca escolhida pelo gabarito.
    melhor = max((False, True), key=lambda com: treinos[com]["f1_validacao"])
    gravar_mencoes(sistemas["CRF + termos" if melhor else "CRF"], textos)

    linhas = []
    for nome, spans in sistemas.items():
        for casamento, m in avaliacao.avaliar_mencoes(spans, gold).items():
            linhas.append({"sistema": nome, "casamento": casamento,
                           **{k: round(v, 4) if isinstance(v, float) else v for k, v in m.items()}})
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    with open(RESULTADOS / "entidades.csv", "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(linhas[0]))
        writer.writeheader()
        writer.writerows(linhas)
    # Menções de cada sistema lado a lado, para inspecionar acertos e erros caso a caso.
    with open(RESULTADOS / "entidades_por_sistema.csv", "w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["sistema", "case_id", "start", "end", "texto"])
        for nome, spans in {"gabarito": gold, **sistemas}.items():
            for case_id, inicio, fim in sorted(spans):
                writer.writerow([nome, case_id, inicio, fim, textos[case_id][inicio:fim]])
    for com, info in treinos.items():
        print(("CRF + termos" if com else "CRF"), info)
    return linhas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("mock", help="gera silver, linha de base das regras e termos (#29 e #32)")
    p_treinar = sub.add_parser("treinar", help="treina o CRF no silver")
    p_treinar.add_argument("--termos", action="store_true", help="usa a pista do termos.csv")
    p_prever = sub.add_parser("prever", help="gera project2/data/mencoes.csv")
    p_prever.add_argument("--termos", action="store_true", help="usa o modelo treinado com a pista dos termos")
    p_prever.add_argument("--todos", action="store_true", help="todos os casos, não só os do gabarito")
    sub.add_parser("comparar", help="treina as duas variantes e gera resultados/entidades.csv")
    args = parser.parse_args()

    if args.comando == "mock":
        print(dados_silver.gerar(), {"termos": termos_mod.gerar()})
    elif args.comando == "treinar":
        print(treinar(args.termos))
    elif args.comando == "prever":
        gold = casos_gold()
        casos = [(c, t) for c, t in ler_casos() if args.todos or c in gold]
        gravar_mencoes(prever(casos, args.termos), dict(casos))
        print(f"{MENCOES.relative_to(REPO)}: {len(casos)} casos")
    else:
        for linha in comparar():
            print(linha)


if __name__ == "__main__":
    main()
