"""Etapa 3: o tipo de cada entidade, pelo léxico do projeto 1 e um classificador para o resto.

    python project2/src/tipos/tipos.py resumo        # menções por tipo no silver e no gabarito

Recebe a tabela de menções da etapa 2 (case_id, id, start, end, texto) e completa cada linha
com tipo, mesh e confiança.
"""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

# Entregas de outras etapas ainda em mock: troque estes imports quando #29 e #32 publicarem.
from mock.comum import DADOS_MOCK, ler_casos
from mock.silver import ler_silver

import lexico

GOLD = DADOS_MOCK / "gold" / "mencoes.csv"
TIPOS = ("Symptom", "History", "Exam", "ExamResult", "Finding",
         "Diagnosis", "Medication", "Treatment", "Outcome", "AnatomicalSite")


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
    o span quase nunca é só o remédio. Os outros tipos passam sem mudança.
    """
    saida = []
    for linha in linhas:
        if linha["tipo"] != "Medication":
            saida.append(linha)
            continue
        trecho = lexico.nome_do_remedio(linha["texto"])
        if trecho:
            inicio, fim = linha["start"] + trecho[0], linha["start"] + trecho[1]
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("resumo", help="menções por tipo no silver (antes e depois da limpeza) e no gabarito")
    args = parser.parse_args()

    if args.comando == "resumo":
        tabela = resumo()
        print(f"{'':16}" + "".join(f"{nome:>10}" for nome in tabela))
        for chave in ("casos", "mencoes", *TIPOS):
            print(f"{chave:16}" + "".join(f"{tabela[nome][chave]:>10}" for nome in tabela))


if __name__ == "__main__":
    main()
