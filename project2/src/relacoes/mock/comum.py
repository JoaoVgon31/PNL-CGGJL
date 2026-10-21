# -*- coding: utf-8 -*-
"""Utilitarios compartilhados pelo gerador de dados mock da Etapa 4.

Versao minima: so o que a Etapa 4 precisa (lista de casos e reserva de
gabarito), sem o tokenizador/tagger que entidades/mock/comum.py e
tipos/mock/comum.py reaproveitam - a Etapa 4 nao re-extrai entidades,
le as do Caio direto de project2/data/mock/silver/mencoes.csv.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import List, Optional, Set, Tuple

REPO = Path(__file__).resolve().parents[4]
CASOS_PADRAO = REPO / "project1" / "data" / "case_texts.csv"
CASOS_GOLD_PADRAO = REPO / "project2" / "data" / "gold" / "casos.txt"


def ler_casos(
    caminho: Path = CASOS_PADRAO, limite: Optional[int] = None
) -> List[Tuple[str, str]]:
    """Pares (case_id, case_text) na ordem do arquivo."""
    with open(caminho, encoding="utf-8", newline="") as handle:
        casos = [(linha["case_id"], linha["case_text"]) for linha in csv.DictReader(handle)]
    return casos[:limite] if limite is not None else casos


def casos_gold(caminho: Path = CASOS_GOLD_PADRAO) -> Set[str]:
    """Casos reservados para gabarito (nunca entram em treino/val/teste)."""
    return {
        linha.strip()
        for linha in Path(caminho).read_text(encoding="utf-8").splitlines()
        if linha.strip()
    }
