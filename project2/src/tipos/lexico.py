"""Linha de base "só léxico": tipo e código de uma menção pelos dicionários do projeto 1.

Fontes, da mais confiável para a menos:
    termos   TERMS do pos_bio.py (lista curada, já com tipo)
    anatomia gazetteer de AnatomicalSite (código ANATnnn)
    mesh     gazetteer do MeSH, com o tipo vindo da categoria (CATEGORIA_TIPO)

Dentro da menção vale o maior trecho que algum dicionário conhece; no empate, a fonte mais
confiável e depois o trecho mais à direita (o núcleo do sintagma em inglês fica no fim).
Sem casamento aproximado: o léxico só responde pelo que conhece com certeza.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from nltk.tokenize import NLTKWordTokenizer

import mock.comum  # noqa: F401  (põe sintagmas/ e dicionarios/ do projeto 1 no path)
from mesh_parser import load_gazetteer_rows, rows_to_raw_gazetteer  # noqa: E402
from normalization import build_normalized_gazetteer, normalize_token  # noqa: E402

GAZETTEERS = mock.comum.PROJECT1_SRC / "dicionarios" / "gazetteer"
CATEGORIA_TIPO = {"drugs": "Medication", "diseases": "Diagnosis", "mental_disorders": "Diagnosis",
                  "treatments": "Treatment", "exams": "Exam", "anatomical_site": "AnatomicalSite"}
# Categorias que juntam tipos diferentes: diseases tem sintomas e achados; drugs (árvore D do
# MeSH) tem os analitos dos exames de sangue (hemoglobin, glucose, C-reactive protein).
AMBIGUAS = frozenset({"diseases", "drugs"})
FONTES = ("termos", "anatomia", "mesh")
# Empate de categoria na mesma chave do MeSH (0,6% das chaves, ex.: biopsy em exams e treatments).
ORDEM_CATEGORIAS = ("termos", "anatomical_site", "exams", "treatments", "drugs", "diseases", "mental_disorders")
JANELA = 6

_TOKENIZADOR = NLTKWordTokenizer()


@dataclass(frozen=True)
class Casamento:
    """Trecho da menção que um dicionário conhece; `inicio`/`fim` são offsets na menção."""
    inicio: int
    fim: int
    tipo: str
    fonte: str
    categoria: str
    codigo: str = ""


@dataclass(frozen=True)
class Resposta:
    tipo: str        # "" quando nenhum dicionário conhece a menção
    mesh: str        # código do MeSH ou do gazetteer anatômico; "" quando não há
    fonte: str       # termos | anatomia | mesh | ""
    categoria: str   # categoria do gazetteer que deu o tipo (para as variantes ambíguas)


@lru_cache(maxsize=1)
def _dicionarios() -> dict[str, dict]:
    """Chave normalizada -> lista de (tipo, categoria, código), por fonte. Carrega uma vez (~3 s)."""
    import pos_bio

    termos = {" ".join(chave): [(tipo, "termos", "")] for chave, tipo in pos_bio.TERM_INDEX.items()}
    anatomia, mesh = {}, {}
    for arquivo, destino in (("anatomical_site_gazetteer.csv", anatomia), ("mesh_gazetteer.csv", mesh)):
        linhas = load_gazetteer_rows(Path(GAZETTEERS) / arquivo)
        for categoria in sorted({linha["category"] for linha in linhas}):
            gaz = build_normalized_gazetteer(rows_to_raw_gazetteer(linhas, category=categoria))
            for chave, entradas in gaz.items():
                codigo = sorted(entradas)[0][0]
                destino.setdefault(chave, []).append((CATEGORIA_TIPO[categoria], categoria, codigo))
    return {"termos": termos, "anatomia": anatomia, "mesh": mesh}


def palavras(texto: str) -> list[tuple[int, int, str]]:
    """(início, fim, palavra normalizada), com o mesmo tokenizador usado nas chaves dos gazetteers."""
    saida = []
    for inicio, fim in _TOKENIZADOR.span_tokenize(texto):
        normal = normalize_token(texto[inicio:fim])
        if normal:
            saida.append((inicio, fim, normal))
    return saida


def _palavra_de_verdade(palavra: str) -> bool:
    """Ao menos 3 letras: evita sinônimos do MeSH como `at 10` (dihidrotaquisterol) casarem com `at 10 mg`."""
    return sum(c.isalpha() for c in palavra) >= 3


def casamentos(texto: str, fontes: tuple[str, ...] = FONTES) -> list[Casamento]:
    """Todos os trechos de até JANELA palavras que algum dicionário conhece."""
    dicionarios = _dicionarios()
    toks = palavras(texto)
    saida = []
    for i in range(len(toks)):
        for j in range(i + 1, min(i + JANELA, len(toks)) + 1):
            if not any(_palavra_de_verdade(t[2]) for t in toks[i:j]):
                continue
            chave = " ".join(t[2] for t in toks[i:j])
            for fonte in fontes:
                for tipo, categoria, codigo in dicionarios[fonte].get(chave, []):
                    saida.append(Casamento(toks[i][0], toks[j - 1][1], tipo, fonte, categoria, codigo))
    return saida


def _melhor(lista: list[Casamento]) -> Casamento | None:
    """Maior trecho; no empate, a fonte mais confiável, o mais à direita e a ORDEM_CATEGORIAS."""
    if not lista:
        return None
    return max(lista, key=lambda c: (c.fim - c.inicio, -FONTES.index(c.fonte), c.fim,
                                     -ORDEM_CATEGORIAS.index(c.categoria)))


def consultar(texto: str) -> Resposta:
    """Tipo pelo melhor casamento; código pelo melhor casamento que tem código."""
    todos = casamentos(texto)
    tipo = _melhor(todos)
    codigo = _melhor([c for c in todos if c.codigo])
    if tipo is None:
        return Resposta("", codigo.codigo if codigo else "", "", "")
    return Resposta(tipo.tipo, codigo.codigo if codigo else "", tipo.fonte, tipo.categoria)


def nome_do_remedio(texto: str) -> tuple[int, int] | None:
    """Offsets do maior remédio dentro do texto, ou None.

    Remédio = TERMS de Medication ou MeSH `drugs`, mas não o que o TERMS chama de Exam
    (hemoglobin, creatinine): na árvore D do MeSH os analitos dos exames são "drugs".
    """
    todos = casamentos(texto)
    exames = {(c.inicio, c.fim) for c in todos if c.fonte == "termos" and c.tipo == "Exam"}
    remedios = [c for c in todos if c.tipo == "Medication" and (c.inicio, c.fim) not in exames]
    melhor = _melhor(remedios)
    return (melhor.inicio, melhor.fim) if melhor else None
