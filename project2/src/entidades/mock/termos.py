"""Mock do termos.csv da #32: termos de 2 a 4 palavras por PMI e C-value, na amostra.

Conta n-gramas dentro de cada frase, nos casos fora do gabarito, e mantém só os que têm forma
de termo segundo o HMM: (ADJ|NOUN)* NOUN. A versão real roda no corpus inteiro.

    C-value(a) = log2|a| * f(a)                                se a não está dentro de outro termo
               = log2|a| * (f(a) - média de f dos termos maiores que contêm a)   caso contrário
    PMI(a)     = log2( P(a) / prod P(w_i) )
"""
from __future__ import annotations

import csv
import math
import re
from collections import Counter
from pathlib import Path

from mock.comum import DADOS_MOCK, casos_gold, dividir_frases, etiquetar, ler_casos, tokenizar

COLUNAS = ["termo", "n", "frequencia", "pmi", "c_value"]
PALAVRA = re.compile(r"^[a-z][a-z0-9-]+$")


def _forma_de_termo(tags: tuple[str, ...]) -> bool:
    return tags[-1] == "NOUN" and all(t in ("ADJ", "NOUN") for t in tags)


def gerar(saida: Path = DADOS_MOCK / "termos.csv", freq_min: int = 2, n_max: int = 4) -> int:
    gold = casos_gold()
    unigramas, ngramas, formas = Counter(), Counter(), {}
    for case_id, texto in ler_casos():
        if case_id in gold:
            continue
        tokens = tokenizar(texto)
        tags = etiquetar(tokens)
        for frase in dividir_frases(texto):
            janela = [(t.text.lower(), tag) for t, tag in zip(tokens, tags)
                      if frase.start <= t.start < frase.end]
            for i, (palavra, _) in enumerate(janela):
                unigramas[palavra] += 1
                for n in range(2, n_max + 1):
                    trecho = janela[i:i + n]
                    if len(trecho) < n or not all(PALAVRA.match(p) for p, _ in trecho):
                        continue
                    chave = tuple(p for p, _ in trecho)
                    ngramas[chave] += 1
                    formas.setdefault(chave, Counter())[tuple(t for _, t in trecho)] += 1

    total = sum(unigramas.values())
    candidatos = {a: f for a, f in ngramas.items()
                  if f >= freq_min and _forma_de_termo(formas[a].most_common(1)[0][0])}
    linhas = []
    for a, f in candidatos.items():
        maiores = [g for b, g in candidatos.items()
                   if len(b) > len(a) and any(b[i:i + len(a)] == a for i in range(len(b) - len(a) + 1))]
        c_value = math.log2(len(a)) * (f - sum(maiores) / len(maiores) if maiores else f)
        pmi = math.log2((f / total) / math.prod(unigramas[w] / total for w in a))
        linhas.append({"termo": " ".join(a), "n": len(a), "frequencia": f,
                       "pmi": round(pmi, 2), "c_value": round(c_value, 2)})
    linhas.sort(key=lambda r: (-r["c_value"], -r["pmi"]))

    saida.parent.mkdir(parents=True, exist_ok=True)
    with open(saida, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUNAS)
        writer.writeheader()
        writer.writerows(linhas)
    return len(linhas)


def ler_termos(caminho: Path = DADOS_MOCK / "termos.csv", limite: int | None = None) -> list[tuple[str, ...]]:
    """Termos como tuplas de palavras minúsculas, do melhor para o pior."""
    with open(caminho, encoding="utf-8", newline="") as handle:
        termos = [tuple(linha["termo"].split()) for linha in csv.DictReader(handle)]
    return termos[:limite] if limite is not None else termos
