"""Silver standard e linha de base das regras do Projeto 1 (#29).

Roda o `combinado.py` do Projeto 1 em cada caso clínico e extrai:
  - Menções com offsets exatos no texto (`case_id,id,start,end,texto,tipo,mesh,polaridade`)
  - Relações resolvidas por sobreposição de offset + tipo (`case_id,origem,destino,relacao`),
    usando `P1` quando a origem é o paciente.
  - Marcação sequencial `bio.conll` (`token\\tpos\\tbio_fronteira\\tbio_tipo`) para os casos de treino.

Os casos reservados em `project2/data/gold/casos.txt` nunca entram em `data/silver/`:
suas extrações pelas regras do Projeto 1 vão para `data/regras/{mencoes,relacoes}.csv`
como linha de base para avaliação no gabarito.
"""
from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[3]
PROJECT1_SRC = REPO / "project1" / "src"
TIPOS_DIR = REPO / "project2" / "src" / "tipos"

for pasta in (
    REPO,
    PROJECT1_SRC / "grafo_lote",
    PROJECT1_SRC,
    PROJECT1_SRC / "tokenizacao",
    PROJECT1_SRC / "sintagmas",
    PROJECT1_SRC / "dicionarios",
    TIPOS_DIR,
):
    if str(pasta) not in sys.path:
        sys.path.insert(0, str(pasta))

from project2.src.comum import (  # noqa: E402
    CASOS_PADRAO,
    GOLD_PADRAO,
    casos_gold,
    dividir_frases,
    etiquetar,
    iter_casos,
    tokenizar,
)

import combinado  # noqa: E402
import lexico  # noqa: E402
from matching import match_text  # noqa: E402
from normalizacao.case_reader import ClinicalCase  # noqa: E402

LOGGER = logging.getLogger(__name__)

DADOS = REPO / "project2" / "data"
SILVER = DADOS / "silver" / "mencoes.csv"
SILVER_RELACOES = DADOS / "silver" / "relacoes.csv"
SILVER_BIO = DADOS / "silver" / "bio.conll"
REGRAS = DADOS / "regras" / "mencoes.csv"
REGRAS_RELACOES = DADOS / "regras" / "relacoes.csv"

TIPOS = {
    "Symptom",
    "History",
    "Exam",
    "ExamResult",
    "Finding",
    "Diagnosis",
    "Medication",
    "Treatment",
    "Outcome",
    "AnatomicalSite",
}
COLUNAS_MENCOES = ["case_id", "id", "start", "end", "texto", "tipo", "mesh", "polaridade"]
COLUNAS_RELACOES = ["case_id", "origem", "destino", "relacao"]


def _parse_attributes(bruto: str | None) -> dict[str, str]:
    if not bruto or not isinstance(bruto, str):
        return {}
    resultado: dict[str, str] = {}
    for parte in bruto.split("; "):
        if "=" in parte:
            chave, valor = parte.split("=", 1)
            resultado[chave.strip()] = valor.strip()
    return resultado


def _resolver_entidade(
    mencoes: list[dict[str, Any]],
    tipo: str,
    char_start: int,
    char_end: int,
    trigger: str,
    texto_caso: str,
) -> dict[str, Any] | None:
    """Menção do tipo certo contida em [char_start, char_end], mais próxima do trigger."""
    candidatas = [
        m for m in mencoes
        if m["tipo"] == tipo and char_start <= m["start"] and m["end"] <= char_end
    ]
    if not candidatas:
        return None
    if len(candidatas) == 1:
        return candidatas[0]
    posicao_trigger = texto_caso.find(trigger, char_start, char_end) if trigger else -1
    referencia = posicao_trigger if posicao_trigger >= 0 else (char_start + char_end) // 2
    return min(candidatas, key=lambda m: abs(((m["start"] + m["end"]) // 2) - referencia))


def resolver_relacoes_do_caso(
    case_id: str,
    texto_caso: str,
    mencoes: list[dict[str, Any]],
    resultado_caso: Any,
) -> list[dict[str, str]]:
    """Resolve arestas clínicas do Projeto 1 para pares (origem, destino, relacao) via offsets."""
    tipos_dos_nos: dict[str, str] = {}
    for _, row in resultado_caso.nos.iterrows():
        tipos_dos_nos[str(row["node_id"])] = str(row["type"])

    relacoes: list[dict[str, str]] = []
    vistos: set[tuple[str, str, str]] = set()

    for _, row in resultado_caso.arestas.iterrows():
        rel = str(row["relation"])
        if rel == "SAME_AS":
            continue
        attrs = _parse_attributes(str(row.get("attributes", "")))
        if "char_start" not in attrs or "char_end" not in attrs:
            continue
        char_start = int(attrs["char_start"])
        char_end = int(attrs["char_end"])
        trigger = attrs.get("trigger", "")

        src_nid = str(row["source_id"])
        tgt_nid = str(row["target_id"])
        tipo_origem = tipos_dos_nos.get(src_nid)
        tipo_destino = tipos_dos_nos.get(tgt_nid)
        if tipo_origem is None or tipo_destino is None:
            continue

        if tipo_origem == "Patient":
            origem_id = "P1"
        else:
            origem = _resolver_entidade(mencoes, tipo_origem, char_start, char_end, trigger, texto_caso)
            if origem is None:
                continue
            origem_id = str(origem["id"])

        destino = _resolver_entidade(mencoes, tipo_destino, char_start, char_end, trigger, texto_caso)
        if destino is None:
            continue
        destino_id = str(destino["id"])

        if origem_id == destino_id:
            continue

        chave = (origem_id, destino_id, rel)
        if chave in vistos:
            continue
        vistos.add(chave)
        relacoes.append(
            {
                "case_id": case_id,
                "origem": origem_id,
                "destino": destino_id,
                "relacao": rel,
            }
        )
    return relacoes


def extrair_caso_regras(
    case_id: str,
    texto: str,
    recursos: Any,
) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[list[tuple[str, str, str, str]]]]:
    """Executa o combinado.py no caso e retorna (mencoes, relacoes, frases_bio)."""
    caso = ClinicalCase(article_id="", age=None, case_id=case_id, case_text=texto, gender="")
    res = combinado.processar_caso(caso, recursos, inspecionar=True)
    inspecao = res.inspecao

    polaridades: dict[tuple[int, int, str], str] = {}
    codigos_sitio: dict[tuple[int, int], str] = {}

    for reg in inspecao["registros"]:
        if not reg["descartar"] and reg["span"]:
            chave = (*reg["span"], reg["tipo"])
            pol = str(reg["attrs"].get("polarity") or "present")
            if polaridades.get(chave) != "absent":
                polaridades[chave] = pol

    for resultado, ref in inspecao["exames_de_resultado"]:
        if ref["span"]:
            chave_ex = (*ref["span"], "Exam")
            polaridades.setdefault(chave_ex, str(ref["attrs"].get("polarity") or "present"))
        bruto = str(resultado.node.attributes.get("raw_text") or "")
        inicio = texto.lower().find(bruto.lower(), resultado.char_start, resultado.char_end) if bruto else -1
        if inicio >= 0:
            polaridades.setdefault((inicio, inicio + len(bruto), "ExamResult"), "present")

    tokens = inspecao["tokens"]
    casamentos = match_text([t.text for t in tokens], recursos.gaz_anatomia)
    for m, linha in zip(casamentos, inspecao["sitios"]):
        inicio, fim = tokens[m.start].start, tokens[m.end - 1].end
        if texto[inicio:fim] != linha["sítio"]:
            raise RuntimeError(f"{case_id}: sítio fora de ordem em {inicio}")
        if not linha["resultado"].startswith("descartado"):
            polaridades.setdefault((inicio, fim, "AnatomicalSite"), "present")
            if linha.get("código"):
                codigos_sitio[(inicio, fim)] = str(linha["código"])

    spans_ordenados = sorted(s for s in polaridades if s[2] in TIPOS and s[0] < s[1])
    mencoes: list[dict[str, Any]] = []
    for k, (inicio, fim, tipo) in enumerate(spans_ordenados, 1):
        trecho = texto[inicio:fim]
        assert trecho, (case_id, inicio, fim)
        codigo = lexico.consultar(trecho).mesh or codigos_sitio.get((inicio, fim), "")
        mencoes.append(
            {
                "case_id": case_id,
                "id": f"s{k}",
                "start": inicio,
                "end": fim,
                "texto": trecho,
                "tipo": tipo,
                "mesh": codigo,
                "polaridade": polaridades[(inicio, fim, tipo)],
            }
        )

    relacoes = resolver_relacoes_do_caso(case_id, texto, mencoes, res)
    frases_bio = _gerar_frases_bio(texto, mencoes)
    return mencoes, relacoes, frases_bio


def mencoes_das_regras(case_id: str, texto: str, recursos: Any) -> list[tuple[int, int, str]]:
    """Spans (start, end, tipo) que as regras ancoram no texto, sem repetição."""
    mencoes, _, _ = extrair_caso_regras(case_id, texto, recursos)
    return [(int(m["start"]), int(m["end"]), str(m["tipo"])) for m in mencoes]


def _gerar_frases_bio(
    texto: str,
    mencoes: list[dict[str, Any]],
) -> list[list[tuple[str, str, str, str]]]:
    """Constrói sentenças no formato (token, pos, bio_fronteira, bio_tipo) sem sobreposição."""
    tokens = tokenizar(texto)
    tags = etiquetar(tokens)

    # Em sobreposições, mantém o span mais longo para marcação BIO plana
    ordenadas = sorted(
        {(int(m["start"]), int(m["end"]), str(m["tipo"])) for m in mencoes},
        key=lambda s: (s[0] - s[1], s[0]),
    )
    planas: list[tuple[int, int, str]] = []
    for ini, fim, tipo in ordenadas:
        if not any(ini < f and i < fim for i, f, _ in planas):
            planas.append((ini, fim, tipo))

    bio_fronteira = ["O"] * len(tokens)
    bio_tipo = ["O"] * len(tokens)
    for ini, fim, tipo in sorted(planas):
        dentro = [k for k, t in enumerate(tokens) if t.start < fim and ini < t.end]
        for pos_idx, k in enumerate(dentro):
            prefixo = "B" if pos_idx == 0 else "I"
            bio_fronteira[k] = prefixo
            bio_tipo[k] = f"{prefixo}-{tipo}"

    frases: list[list[tuple[str, str, str, str]]] = []
    for frase in dividir_frases(texto):
        sent: list[tuple[str, str, str, str]] = []
        for k, (tok, tag) in enumerate(zip(tokens, tags)):
            if frase.start <= tok.start < frase.end:
                sent.append((tok.text, tag, bio_fronteira[k], bio_tipo[k]))
        if sent:
            frases.append(sent)
    return frases


def gravar_csv(linhas: list[dict[str, Any]], caminho: Path, colunas: list[str]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=colunas, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(linhas)


def gravar_conll(frases: list[list[tuple[str, str, str, str]]], caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="\n") as handle:
        for frase in frases:
            for tok, pos, bio_b, bio_t in frase:
                handle.write(f"{tok}\t{pos}\t{bio_b}\t{bio_t}\n")
            handle.write("\n")


def ler_silver(caminho: Path = SILVER, gold_path: Path = GOLD_PADRAO) -> list[dict[str, Any]]:
    """Linhas do silver com `start`/`end` inteiros, garantindo exclusão dos casos do gabarito."""
    if not caminho.is_file():
        raise FileNotFoundError(
            f"{caminho} não existe: rode `python project2/src/dados/silver.py` antes"
        )
    gold = casos_gold(gold_path)
    with open(caminho, encoding="utf-8", newline="") as handle:
        linhas = [linha for linha in csv.DictReader(handle) if linha["case_id"] not in gold]
    for linha in linhas:
        linha["start"], linha["end"] = int(linha["start"]), int(linha["end"])
    return linhas


def gerar(
    saida: Path = DADOS,
    casos: Path = CASOS_PADRAO,
    gold_path: Path = GOLD_PADRAO,
    limite: int | None = None,
) -> dict[str, int]:
    """Gera `data/silver/{mencoes.csv,relacoes.csv,bio.conll}` e `data/regras/{mencoes.csv,relacoes.csv}`."""
    gold = casos_gold(gold_path)
    recursos = combinado.carregar_recursos()

    silver_mencoes: list[dict[str, Any]] = []
    silver_relacoes: list[dict[str, str]] = []
    silver_bio: list[list[tuple[str, str, str, str]]] = []
    regras_mencoes: list[dict[str, Any]] = []
    regras_relacoes: list[dict[str, str]] = []

    for case_id, texto in iter_casos(casos, limite=limite):
        try:
            mencoes, relacoes, frases_bio = extrair_caso_regras(case_id, texto, recursos)
        except Exception:
            LOGGER.exception("regras falharam em %s; caso ignorado", case_id)
            continue

        if case_id in gold:
            regras_mencoes.extend(mencoes)
            regras_relacoes.extend(relacoes)
        else:
            silver_mencoes.extend(mencoes)
            silver_relacoes.extend(relacoes)
            silver_bio.extend(frases_bio)

    gravar_csv(silver_mencoes, saida / "silver" / "mencoes.csv", COLUNAS_MENCOES)
    gravar_csv(silver_relacoes, saida / "silver" / "relacoes.csv", COLUNAS_RELACOES)
    gravar_conll(silver_bio, saida / "silver" / "bio.conll")
    gravar_csv(regras_mencoes, saida / "regras" / "mencoes.csv", COLUNAS_MENCOES)
    gravar_csv(regras_relacoes, saida / "regras" / "relacoes.csv", COLUNAS_RELACOES)

    return {
        "silver": len(silver_mencoes),
        "silver_relacoes": len(silver_relacoes),
        "silver_frases_bio": len(silver_bio),
        "regras": len(regras_mencoes),
        "regras_relacoes": len(regras_relacoes),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--casos", type=Path, default=CASOS_PADRAO, help="CSV ou Parquet de casos")
    parser.add_argument("--gold", type=Path, default=GOLD_PADRAO, help="Lista de casos do gabarito")
    parser.add_argument("--saida", type=Path, default=DADOS, help="Diretório base de saída (project2/data)")
    parser.add_argument("--limite", type=int, help="Processa só os N primeiros casos")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print(gerar(saida=args.saida, casos=args.casos, gold_path=args.gold, limite=args.limite))


if __name__ == "__main__":
    main()
