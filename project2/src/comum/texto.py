"""Mesmos algoritmos do projeto 1, sem imports de nomes globais como models/tokenizers."""
from __future__ import annotations

from functools import lru_cache

from project1.src.tokenizacao.tokenizers import ClinicalRegexTokenizer
from project1.src.stopwords.extractors.common import Sentence, split_sentences
from project1.src.sintagmas import pos_bio

_TOKENIZADOR = ClinicalRegexTokenizer()


def tokenizar(texto: str) -> list:
    """Tokens com text/start/end/index/kind; texto[start:end] == text."""
    return _TOKENIZADOR.tokenize(texto)


def dividir_frases(texto: str) -> list[Sentence]:
    """Preserva o contrato P1: pontuação final excluída, espaços e offsets preservados."""
    if not isinstance(texto, str):
        raise TypeError("texto deve ser str")
    return [s for s in split_sentences(texto) if s.text.strip()]


@lru_cache(maxsize=1)
def _tagger():
    return pos_bio.HMMTagger()


def etiquetar(tokens: list) -> list[str]:
    """HMM do P1 com restrições e reparos; índices locais para também aceitar uma frase."""
    if not tokens:
        return []
    adaptados = [pos_bio.Token(t.text, t.start, t.end, i) for i, t in enumerate(tokens)]
    for t, adaptado in zip(tokens, adaptados):
        if t.kind == "UNIT":
            adaptado.role = "UNIT"
    tagger = _tagger()
    restricoes = pos_bio.build_constraints(adaptados, tagger, pos_bio.HEAD_NOUNS)
    for i, t in enumerate(tokens):
        if t.kind == "FIGURE_REF":
            restricoes[i] = {"."}
    tagger.tag(adaptados, restricoes)
    pos_bio.repair_tags(adaptados)
    return [t.tag for t in adaptados]
