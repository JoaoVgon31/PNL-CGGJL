"""Leitura incremental de CSV e dos Parquet planos ou aninhados do MultiCaRe."""
from __future__ import annotations

import csv
import re
from collections.abc import Iterator
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CASOS_PADRAO = REPO / "project1/data/case_texts.csv"
GOLD_PADRAO = REPO / "project2/data/gold/casos.txt"
csv.field_size_limit(10 ** 9)


def _parquet(caminho: Path) -> Iterator[dict]:
    try:
        import duckdb
    except ImportError as error:
        raise RuntimeError("Para Parquet/coleta: pip install -r project2/src/comum/requirements.txt") from error
    with duckdb.connect() as db:
        campos = {r[0] for r in db.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(caminho)]).fetchall()}
        if {"case_id", "case_text"} <= campos:
            sql = "SELECT * FROM read_parquet(?)"
        elif {"article_id", "cases"} <= campos:
            sql = ("SELECT article_id, c.age AS age, c.case_id AS case_id, "
                   "c.case_text AS case_text, c.gender AS gender FROM "
                   "(SELECT article_id, unnest(cases) AS c FROM read_parquet(?))")
        else:
            raise ValueError("Parquet precisa de case_id/case_text ou article_id/cases")
        cursor = db.execute(sql, [str(caminho)])
        nomes = [c[0] for c in cursor.description]
        while lote := cursor.fetchmany(512):
            for valores in lote:
                yield dict(zip(nomes, valores))


def iter_registros(caminho: Path | str = CASOS_PADRAO, limite: int | None = None) -> Iterator[dict]:
    """Registros originais, incluindo metadados quando disponíveis; sem alterar case_text."""
    if limite is not None and limite < 0:
        raise ValueError("limite deve ser >= 0")
    caminho = Path(caminho)
    if not caminho.is_file():
        raise FileNotFoundError(caminho)
    if limite == 0:
        return
    if caminho.suffix.lower() == ".parquet":
        registros = _parquet(caminho)
        try:
            yield from _validar(registros, limite)
        finally:
            registros.close()
    else:
        with caminho.open(encoding="utf-8-sig", newline="") as handle:
            leitor = csv.DictReader(handle)
            if not {"case_id", "case_text"} <= set(leitor.fieldnames or []):
                raise ValueError("CSV precisa das colunas case_id e case_text")
            yield from _validar(leitor, limite)


def _validar(registros, limite):
    vistos = set()
    for i, linha in enumerate(registros):
        case_id, texto = linha.get("case_id"), linha.get("case_text")
        if not isinstance(case_id, str) or not case_id.strip() or not isinstance(texto, str):
            raise ValueError(f"Caso inválido na linha {i + 2}: case_id/case_text ausente")
        if case_id in vistos:
            raise ValueError(f"case_id duplicado: {case_id}")
        vistos.add(case_id)
        yield linha
        if limite is not None and i + 1 >= limite:
            return


def iter_casos(caminho: Path | str = CASOS_PADRAO, limite: int | None = None) -> Iterator[tuple[str, str]]:
    """Pares (case_id, case_text), sem carregar os textos do corpus inteiro na memória."""
    for linha in iter_registros(caminho, limite):
        yield linha["case_id"], linha["case_text"]


def ler_casos(caminho: Path | str = CASOS_PADRAO, limite: int | None = None) -> list[tuple[str, str]]:
    """Versão em lista compatível com as etapas 2/3; para corpus inteiro prefira iter_casos."""
    return list(iter_casos(caminho, limite))


def casos_gold(caminho: Path | str = GOLD_PADRAO) -> set[str]:
    """Falha se a lista não existir ou estiver vazia: nunca assume que treino está liberado."""
    caminho = Path(caminho)
    if not caminho.is_file():
        raise FileNotFoundError(f"Gabarito ausente: {caminho}. Obtenha a lista da #29 ou passe --gold explicitamente.")
    ids = {l.strip() for l in caminho.read_text(encoding="utf-8-sig").splitlines()
           if l.strip() and not l.lstrip().startswith("#")}
    if not ids or any(re.fullmatch(r"PMC\d+_\d+", c) is None for c in ids):
        raise ValueError("Lista do gabarito vazia ou com identificadores inválidos")
    return ids
