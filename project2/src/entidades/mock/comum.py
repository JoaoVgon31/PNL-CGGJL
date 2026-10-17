"""Mock do módulo comum da #32: texto, tokens com offsets, frases e lista do gabarito.

Reaproveita o tokenizador e o divisor de frases do projeto 1, que é o que a #32 vai publicar.
Quando `project2/src/comum/` existir, troque o import em `entidades.py` e apague este arquivo.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
PROJECT1_SRC = REPO / "project1" / "src"
DADOS_MOCK = REPO / "project2" / "data" / "mock"
CASOS_PADRAO = REPO / "project1" / "data" / "case_texts.csv"

# Mesmas pastas que o combinado.py põe no path: pacotes em src/ e pastas planas com módulos de nome único.
for pasta in (PROJECT1_SRC / "grafo_lote", PROJECT1_SRC, PROJECT1_SRC / "tokenizacao",
              PROJECT1_SRC / "sintagmas", PROJECT1_SRC / "dicionarios"):
    if str(pasta) not in sys.path:
        sys.path.append(str(pasta))

from stopwords.extractors.common import Sentence, split_sentences  # noqa: E402
from tokenizers import ClinicalRegexTokenizer  # noqa: E402

csv.field_size_limit(10 ** 9)
_TOKENIZADOR = ClinicalRegexTokenizer()


def ler_casos(caminho: Path | str = CASOS_PADRAO, limite: int | None = None) -> list[tuple[str, str]]:
    """Pares (case_id, case_text) na ordem do arquivo."""
    with open(caminho, encoding="utf-8", newline="") as handle:
        casos = [(linha["case_id"], linha["case_text"]) for linha in csv.DictReader(handle)]
    return casos[:limite] if limite is not None else casos


def tokenizar(texto: str) -> list:
    """Tokens com `text`, `start`, `end`, `index` e `kind`."""
    return _TOKENIZADOR.tokenize(texto)


def dividir_frases(texto: str) -> list[Sentence]:
    """Frases com `start` e `end`; a pontuação final fica de fora da frase."""
    return [s for s in split_sentences(texto) if s.text.strip()]


_TAGGER = None


def etiquetar(tokens: list) -> list[str]:
    """Classe gramatical do HMM do projeto 1, com as mesmas restrições e reparos do combinado.py."""
    import pos_bio

    global _TAGGER
    if _TAGGER is None:
        _TAGGER = pos_bio.HMMTagger()
    ptokens = []
    for t in tokens:
        pt = pos_bio.Token(t.text, t.start, t.end, t.index)
        if t.kind == "UNIT":
            pt.role = "UNIT"
        ptokens.append(pt)
    restricoes = pos_bio.build_constraints(ptokens, _TAGGER, pos_bio.HEAD_NOUNS)
    for i, t in enumerate(tokens):
        if t.kind == "FIGURE_REF":
            restricoes[i] = {"."}
    _TAGGER.tag(ptokens, restricoes)
    pos_bio.repair_tags(ptokens)
    return [pt.tag for pt in ptokens]


def casos_gold(caminho: Path | str = DADOS_MOCK / "gold" / "casos.txt") -> set[str]:
    """Casos que nunca entram em treino."""
    return {linha.strip() for linha in Path(caminho).read_text(encoding="utf-8").splitlines() if linha.strip()}
