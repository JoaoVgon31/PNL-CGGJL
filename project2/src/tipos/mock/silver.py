"""Mock do silver da #29: menções tipadas pelas regras do projeto 1.

Não gera nada: lê o `data/mock/silver/mencoes.csv` que a etapa 2 já produz com
`python project2/src/entidades/entidades.py mock`, para que as duas etapas treinem no mesmo silver.
Formato: case_id,id,start,end,texto,tipo.
"""
from __future__ import annotations

import csv
from pathlib import Path

from mock.comum import DADOS_MOCK, casos_gold

SILVER = DADOS_MOCK / "silver" / "mencoes.csv"


def ler_silver(caminho: Path = SILVER) -> list[dict]:
    """Linhas do silver com `start`/`end` inteiros, sem os casos do gabarito."""
    if not caminho.is_file():
        raise FileNotFoundError(f"{caminho} não existe: rode `python project2/src/entidades/entidades.py mock`")
    gold = casos_gold()
    with open(caminho, encoding="utf-8", newline="") as handle:
        linhas = [linha for linha in csv.DictReader(handle) if linha["case_id"] not in gold]
    for linha in linhas:
        linha["start"], linha["end"] = int(linha["start"]), int(linha["end"])
    return linhas
