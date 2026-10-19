"""Etapa 3: o tipo de cada entidade, pelo léxico do projeto 1 e um classificador para o resto.

    python project2/src/tipos/tipos.py resumo        # menções por tipo no silver e no gabarito
    python project2/src/tipos/tipos.py treinar       # regressão logística no silver
    python project2/src/tipos/tipos.py tipar [--modo M] [--entrada CSV]   # gera mencoes_tipadas.csv
    python project2/src/tipos/tipos.py comparar      # os 4 modos no gabarito -> data/resultados/tipos*.csv

Recebe a tabela de menções da etapa 2 (case_id, id, start, end, texto) e completa cada linha
com tipo, mesh e confiança. O classificador vê três coisas de cada menção: os N-gramas de
caracteres e de palavras do texto dela e as palavras ao redor, com TF-IDF.
"""
from __future__ import annotations

import argparse
import csv
import pickle
import time
from collections import Counter
from pathlib import Path

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

# Entregas de outras etapas ainda em mock: troque estes imports quando #29 e #32 publicarem.
from mock import avaliar as avaliacao
from mock.comum import DADOS_MOCK, REPO, casos_gold, ler_casos
from mock.silver import ler_silver

import lexico

GOLD = DADOS_MOCK / "gold" / "mencoes.csv"
MENCOES = REPO / "project2" / "data" / "mencoes.csv"
TIPADAS = REPO / "project2" / "data" / "mencoes_tipadas.csv"
RESULTADOS = REPO / "project2" / "data" / "resultados"
MODELO = REPO / "project2" / "models" / "tipos" / "classificador.pkl"
TIPOS = ("Symptom", "History", "Exam", "ExamResult", "Finding",
         "Diagnosis", "Medication", "Treatment", "Outcome", "AnatomicalSite")
CONTEXTO = 3  # palavras de cada lado
GRADE = [(c, peso) for c in (0.3, 1.0, 3.0, 10.0) for peso in (None, "balanced")]
LIMIARES = [k / 20 for k in range(0, 20)]
# Quem dá o tipo em cada sistema comparado; o código (mesh) vem sempre do léxico.
MODOS = {
    "lexico": "só o léxico",
    "lexico+classificador": "o léxico; o classificador tipa o que o léxico não conhece",
    "ambiguas": "como o anterior, mas o classificador decide também em diseases/drugs do MeSH",
    "classificador": "só o classificador",
}
COLUNAS = ["case_id", "id", "start", "end", "texto", "tipo", "mesh", "confianca", "fonte"]


# ======================================================================= dados ==
def ler_mencoes(caminho: Path) -> list[dict]:
    """Linhas de uma tabela de menções, com `start`/`end` inteiros."""
    with open(caminho, encoding="utf-8", newline="") as handle:
        linhas = list(csv.DictReader(handle))
    for linha in linhas:
        linha["start"], linha["end"] = int(linha["start"]), int(linha["end"])
    return linhas


def limpar_silver(linhas: list[dict]) -> list[dict]:
    """Medication do silver só com o nome do remédio; sem remédio conhecido, a menção sai.

    A regra de dose do projeto 1 pega as 3 palavras antes da dose (`a dose of 5 mg`, `BUN 17 mg`):
    o span quase nunca é só o remédio. Os outros tipos passam sem mudança. Se o nome que sobra já é
    uma menção de outro tipo no silver (`aspartate transaminase` como Exam), a de Medication sai.
    """
    outros = {(x["case_id"], x["start"], x["end"]) for x in linhas if x["tipo"] != "Medication"}
    saida = []
    for linha in linhas:
        if linha["tipo"] != "Medication":
            saida.append(linha)
            continue
        trecho = lexico.nome_do_remedio(linha["texto"])
        if trecho:
            inicio, fim = linha["start"] + trecho[0], linha["start"] + trecho[1]
            if (linha["case_id"], inicio, fim) not in outros:
                saida.append({**linha, "start": inicio, "end": fim, "texto": linha["texto"][trecho[0]:trecho[1]]})
    return saida


def resumo() -> dict[str, dict[str, int]]:
    """Menções por tipo no silver (antes e depois da limpeza) e no gabarito, e o número de casos."""
    textos = ler_casos()
    saida = {}
    silver = ler_silver()
    for nome, linhas in (("silver", silver), ("limpo", limpar_silver(silver)), ("gabarito", ler_mencoes(GOLD))):
        for linha in linhas:
            assert textos[linha["case_id"]][linha["start"]:linha["end"]] == linha["texto"], linha
        contagem = Counter(linha["tipo"] for linha in linhas)
        saida[nome] = {"casos": len({linha["case_id"] for linha in linhas}), "mencoes": len(linhas),
                       **{tipo: contagem[tipo] for tipo in TIPOS}}
    return saida


# ===================================================================== pistas ==
def pistas(mencoes: list[dict], textos: dict[str, str]) -> pd.DataFrame:
    """Uma linha por menção: o texto dela e as palavras ao redor, marcadas pelo lado.

    `presented with ___ associated` vira contexto "E:presented E:with D:associated": a mesma palavra
    antes e depois da menção são pistas diferentes.
    """
    palavras_do_caso = {}
    linhas = []
    for m in mencoes:
        if m["case_id"] not in palavras_do_caso:
            palavras_do_caso[m["case_id"]] = lexico.palavras(textos[m["case_id"]])
        toks = palavras_do_caso[m["case_id"]]
        antes = [p for ini, fim, p in toks if fim <= m["start"]][-CONTEXTO:]
        depois = [p for ini, fim, p in toks if ini >= m["end"]][:CONTEXTO]
        contexto = [f"E:{p}" for p in antes] + [f"D:{p}" for p in depois]
        linhas.append({"mencao": m["texto"].lower(), "contexto": " ".join(contexto)})
    return pd.DataFrame(linhas, columns=["mencao", "contexto"])


def novo_classificador(c: float, peso: str | None) -> Pipeline:
    """TF-IDF de caracteres (2-5) e palavras (1-2) da menção, palavras do contexto, e regressão logística."""
    vetores = ColumnTransformer([
        ("caracteres", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True), "mencao"),
        ("palavras", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True), "mencao"),
        ("contexto", TfidfVectorizer(token_pattern=r"\S+", lowercase=False, sublinear_tf=True), "contexto"),
    ])
    return Pipeline([("vetores", vetores),
                     ("modelo", LogisticRegression(C=c, class_weight=peso, max_iter=5000))])


# ===================================================================== treino ==
def separar(linhas: list[dict]) -> tuple[list[dict], list[dict]]:
    """Treino e validação por caso: 1 caso em cada 5 vai para a validação (menções do mesmo caso juntas)."""
    casos = sorted({linha["case_id"] for linha in linhas})
    validacao = set(casos[::5])
    return ([x for x in linhas if x["case_id"] not in validacao],
            [x for x in linhas if x["case_id"] in validacao])


def aplicar_limiar(probabilidades, classes, limiar: float) -> list[tuple[str, float]]:
    """(tipo, confiança) por menção; abaixo do limiar o tipo fica vazio."""
    saida = []
    for linha in probabilidades:
        k = linha.argmax()
        saida.append((classes[k] if linha[k] >= limiar else "", float(linha[k])))
    return saida


def _avaliar(mencoes: list[dict], previstos: list[tuple[str, float]]) -> dict:
    pred = [{**m, "tipo": tipo} for m, (tipo, _) in zip(mencoes, previstos)]
    return avaliacao.avaliar_tipos(pred, mencoes)


def _f1_micro(m: dict) -> float:
    """Acertos sobre tipadas (precisão) e sobre todas (acurácia): o limiar troca uma pela outra."""
    precisao = m["acuracia"] / m["cobertura"] if m["cobertura"] else 0.0
    return 2 * precisao * m["acuracia"] / (precisao + m["acuracia"]) if precisao + m["acuracia"] else 0.0


def treinar() -> dict:
    """Escolhe C e peso das classes pelo macro F1 na validação, o limiar pelo F1 micro, e retreina em tudo."""
    textos = ler_casos()
    linhas = limpar_silver(ler_silver())
    treino, validacao = separar(linhas)
    X_tr, y_tr = pistas(treino, textos), [x["tipo"] for x in treino]
    X_va = pistas(validacao, textos)

    notas = []
    for c, peso in GRADE:
        clf = novo_classificador(c, peso).fit(X_tr, y_tr)
        probabilidades = clf.predict_proba(X_va)
        sem_limiar = _avaliar(validacao, aplicar_limiar(probabilidades, clf.classes_, 0.0))
        limiar = max(LIMIARES, key=lambda t: (_f1_micro(_avaliar(validacao, aplicar_limiar(probabilidades, clf.classes_, t))), -t))
        notas.append((sem_limiar["macro_f1"], c, str(peso), limiar))
    macro_f1, c, peso, limiar = max(notas, key=lambda n: (n[0], -n[1]))
    peso = None if peso == "None" else peso

    inicio = time.perf_counter()
    clf = novo_classificador(c, peso).fit(pistas(linhas, textos), [x["tipo"] for x in linhas])
    tempo = time.perf_counter() - inicio

    MODELO.parent.mkdir(parents=True, exist_ok=True)
    with open(MODELO, "wb") as handle:
        pickle.dump({"classificador": clf, "limiar": limiar}, handle)
    return {"modelo": str(MODELO.relative_to(REPO)), "mencoes": len(linhas), "treino": len(treino),
            "validacao": len(validacao), "C": c, "peso": peso, "limiar": limiar,
            "macro_f1_validacao": round(macro_f1, 4), "tempo_treino_s": round(tempo, 1)}


def classificar(mencoes: list[dict], textos: dict[str, str]) -> list[tuple[str, float]]:
    """(tipo, confiança) do classificador salvo; tipo vazio quando a confiança fica abaixo do limiar."""
    if not mencoes:
        return []
    if not MODELO.is_file():
        raise FileNotFoundError(f"{MODELO} não existe: rode `treinar` antes")
    with open(MODELO, "rb") as handle:
        salvo = pickle.load(handle)
    clf = salvo["classificador"]
    return aplicar_limiar(clf.predict_proba(pistas(mencoes, textos)), clf.classes_, salvo["limiar"])


# =================================================================== tipagem ==
def tipar(mencoes: list[dict], textos: dict[str, str], modo: str = "lexico+classificador") -> list[dict]:
    """As mesmas menções com tipo, mesh, confianca e fonte (lexico | classificador | "").

    O léxico responde com confiança 1. No modo `ambiguas`, se o classificador ficar abaixo do limiar
    numa menção de categoria ambígua, o tipo do léxico é mantido: a variante não perde cobertura.
    """
    if modo not in MODOS:
        raise ValueError(f"modo {modo!r}; use um de {sorted(MODOS)}")
    respostas = [lexico.consultar(m["texto"]) for m in mencoes]
    saida = [{**m, "tipo": r.tipo, "mesh": r.mesh, "confianca": 1.0 if r.tipo else 0.0,
              "fonte": "lexico" if r.tipo else ""} for m, r in zip(mencoes, respostas)]
    if modo == "lexico":
        return saida

    def precisa(r: lexico.Resposta) -> bool:
        if modo == "classificador":
            return True
        return not r.tipo or (modo == "ambiguas" and r.categoria in lexico.AMBIGUAS)

    indices = [k for k, r in enumerate(respostas) if precisa(r)]
    for k, (tipo, confianca) in zip(indices, classificar([mencoes[k] for k in indices], textos)):
        if tipo:
            saida[k].update(tipo=tipo, confianca=round(confianca, 4), fonte="classificador")
        elif modo == "classificador":
            saida[k].update(tipo="", confianca=round(confianca, 4), fonte="")
    return saida


def gravar_tipadas(linhas: list[dict], caminho: Path = TIPADAS) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUNAS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(linhas)


# ================================================================== comparação ==
def _gravar_csv(caminho: Path, linhas: list[dict]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(linhas[0]))
        writer.writeheader()
        writer.writerows(linhas)


def comparar() -> list[dict]:
    """Retreina e mede os 4 modos no gabarito, em duas entradas:

    gabarito  as fronteiras do gabarito: mede só a tipagem (casamento exato, os pares são perfeitos)
    crf       as menções da etapa 2 (data/mencoes.csv): ponta a ponta, exato e por sobreposição

    Grava em data/resultados/: tipos.csv (uma linha por sistema), tipos_confusao.csv e
    tipos_por_mencao.csv (o tipo de cada modo lado a lado, nas fronteiras do gabarito).
    """
    print("treino:", treinar())
    textos = ler_casos()
    gold = ler_mencoes(GOLD)
    entradas = {"gabarito": (gold, (True,))}
    if MENCOES.is_file():
        ids = casos_gold()
        entradas["crf"] = ([m for m in ler_mencoes(MENCOES) if m["case_id"] in ids], (True, False))
    else:
        print(f"{MENCOES.relative_to(REPO)} não existe: rode `entidades.py prever` para a linha ponta a ponta")

    linhas, confusao, por_modo = [], [], {}
    for entrada, (mencoes, casamentos) in entradas.items():
        for modo in MODOS:
            tipadas = tipar(mencoes, textos, modo)
            if entrada == "gabarito":
                por_modo[modo] = tipadas
            for exato in casamentos:
                m = avaliacao.avaliar_tipos(tipadas, gold, exato)
                casamento = "exato" if exato else "sobreposicao"
                linhas.append({"sistema": modo, "entrada": entrada, "casamento": casamento,
                               "cobertura": round(m["cobertura"], 4), "acuracia": round(m["acuracia"], 4),
                               "macro_f1": round(m["macro_f1"], 4), "n_pred": m["n_pred"], "n_gold": m["n_gold"],
                               **{f"f1_{t}": round(m["por_tipo"][t]["f1"], 4) for t in TIPOS if t in m["por_tipo"]}})
                confusao += [{"sistema": modo, "entrada": entrada, "casamento": casamento,
                              "gold": g, "previsto": p or "(sem tipo)", "n": n}
                             for (g, p), n in sorted(m["confusao"].items())]

    lado_a_lado = [{"case_id": g["case_id"], "start": g["start"], "end": g["end"], "texto": g["texto"],
                    "gabarito": g["tipo"], **{modo: por_modo[modo][k]["tipo"] for modo in MODOS}}
                   for k, g in enumerate(gold)]
    _gravar_csv(RESULTADOS / "tipos.csv", linhas)
    _gravar_csv(RESULTADOS / "tipos_confusao.csv", confusao)
    _gravar_csv(RESULTADOS / "tipos_por_mencao.csv", lado_a_lado)
    return linhas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("resumo", help="menções por tipo no silver (antes e depois da limpeza) e no gabarito")
    sub.add_parser("treinar", help="treina a regressão logística no silver")
    p_tipar = sub.add_parser("tipar", help="completa uma tabela de menções com tipo e mesh")
    p_tipar.add_argument("--modo", choices=sorted(MODOS), default="lexico+classificador")
    p_tipar.add_argument("--entrada", type=Path, default=MENCOES,
                         help="tabela de menções (padrão: saída da etapa 2; use o gabarito para as fronteiras dele)")
    p_tipar.add_argument("--saida", type=Path, default=TIPADAS)
    sub.add_parser("comparar", help="retreina e mede os 4 modos no gabarito; grava data/resultados/tipos*.csv")
    args = parser.parse_args()

    if args.comando == "resumo":
        tabela = resumo()
        print(f"{'':16}" + "".join(f"{nome:>10}" for nome in tabela))
        for chave in ("casos", "mencoes", *TIPOS):
            print(f"{chave:16}" + "".join(f"{tabela[nome][chave]:>10}" for nome in tabela))
    elif args.comando == "treinar":
        print(treinar())
    elif args.comando == "tipar":
        if not args.entrada.is_file():
            raise SystemExit(f"{args.entrada} não existe: rode `entidades.py prever` ou passe --entrada")
        linhas = tipar(ler_mencoes(args.entrada), ler_casos(), args.modo)
        gravar_tipadas(linhas, args.saida)
        fontes = Counter(linha["fonte"] or "sem tipo" for linha in linhas)
        print(f"{args.saida}: {len(linhas)} menções, {dict(fontes)}")
    else:
        print(f"{'sistema':22}{'entrada':10}{'casamento':14}{'cobertura':>10}{'acuracia':>10}{'macro_f1':>10}")
        for linha in comparar():
            print(f"{linha['sistema']:22}{linha['entrada']:10}{linha['casamento']:14}"
                  f"{linha['cobertura']:>10.2f}{linha['acuracia']:>10.2f}{linha['macro_f1']:>10.2f}")


if __name__ == "__main__":
    main()
