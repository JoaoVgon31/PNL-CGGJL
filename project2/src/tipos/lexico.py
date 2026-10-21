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
import re
import sys

from nltk.tokenize import NLTKWordTokenizer

REPO = Path(__file__).resolve().parents[3]
PROJECT1_SRC = REPO / "project1" / "src"
for _pasta in (REPO, PROJECT1_SRC / "sintagmas", PROJECT1_SRC / "dicionarios"):
    if str(_pasta) not in sys.path:
        sys.path.insert(0, str(_pasta))

from mesh_parser import load_gazetteer_rows, rows_to_raw_gazetteer  # noqa: E402
from normalization import build_normalized_gazetteer, normalize_token  # noqa: E402

GAZETTEERS = PROJECT1_SRC / "dicionarios" / "gazetteer"
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
_PADRAO_SIGLA = re.compile(r"\(\s*([A-Z][A-Z0-9\-]{1,9})\s*\)")
_QUEBRA_TRECHO = re.compile(r"[,;:.()\n]")


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


def _consultar_direto(texto: str) -> Resposta:
    todos = casamentos(texto)
    tipo = _melhor(todos)
    codigo = _melhor([c for c in todos if c.codigo])
    if tipo is None:
        return Resposta("", codigo.codigo if codigo else "", "", "")
    return Resposta(tipo.tipo, codigo.codigo if codigo else "", tipo.fonte, tipo.categoria)


@lru_cache(maxsize=256)
def siglas_do_texto(texto_caso: str) -> dict[str, Resposta]:
    """Mapeia siglas definidas no caso (`Forma Extensa (SIGLA)`) para a Resposta da forma extensa."""
    if not texto_caso:
        return {}
    mapa: dict[str, Resposta] = {}
    for m in _PADRAO_SIGLA.finditer(texto_caso):
        sigla = m.group(1).strip()
        janela = texto_caso[max(0, m.start() - 80):m.start()]
        partes = _QUEBRA_TRECHO.split(janela)
        trecho_antes = partes[-1].strip() if partes else ""
        if not trecho_antes:
            continue
        toks = palavras(trecho_antes)
        if not toks:
            continue
        # Prioriza casamentos ancorados no fim do sintagma imediatamente antes do parêntese
        fim_ultimo = toks[-1][1]
        todos = casamentos(trecho_antes)
        no_fim = [c for c in todos if c.fim == fim_ultimo]
        escolhidos = no_fim if no_fim else todos
        tipo = _melhor(escolhidos)
        codigo = _melhor([c for c in escolhidos if c.codigo])
        if tipo is not None:
            mapa[sigla] = Resposta(
                tipo.tipo,
                codigo.codigo if codigo else "",
                tipo.fonte,
                tipo.categoria,
            )
    return mapa


def consultar(texto: str, texto_caso: str = "") -> Resposta:
    """Tipo pelo melhor casamento; código pelo melhor casamento que tem código.

    Quando `texto_caso` é informado e `texto` é uma sigla definida no próprio caso
    (`transesophageal echocardiogram (TEE)`), herda o tipo e o código da forma extensa.
    """
    limpo = texto.strip()
    if texto_caso and limpo:
        definidas = siglas_do_texto(texto_caso)
        if limpo in definidas:
            return definidas[limpo]
    return _consultar_direto(texto)


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
