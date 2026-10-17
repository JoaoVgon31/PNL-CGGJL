"""Mock do módulo comum da #32: texto dos casos, lista do gabarito e caminho do projeto 1.

Quando `project2/src/comum/` existir, troque o import em `tipos.py` e apague este arquivo.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROJECT1_SRC = REPO / "project1" / "src"
DADOS_MOCK = REPO / "project2" / "data" / "mock"
CASOS_PADRAO = REPO / "project1" / "data" / "case_texts.csv"

# O léxico usa o pos_bio.py (sintagmas/) e os gazetteers (dicionarios/) do projeto 1.
for pasta in (PROJECT1_SRC / "sintagmas", PROJECT1_SRC / "dicionarios"):
    if str(pasta) not in sys.path:
        sys.path.append(str(pasta))

csv.field_size_limit(10 ** 9)


def ler_casos(caminho: Path | str = CASOS_PADRAO) -> dict[str, str]:
    """{case_id: case_text}, na ordem do arquivo."""
    with open(caminho, encoding="utf-8", newline="") as handle:
        return {linha["case_id"]: linha["case_text"] for linha in csv.DictReader(handle)}


def casos_gold(caminho: Path | str = DADOS_MOCK / "gold" / "casos.txt") -> set[str]:
    """Casos que nunca entram em treino."""
    return {linha.strip() for linha in Path(caminho).read_text(encoding="utf-8").splitlines() if linha.strip()}
