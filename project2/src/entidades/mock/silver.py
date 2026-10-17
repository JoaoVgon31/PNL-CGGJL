"""Mock do silver da #29: menções das regras do projeto 1 com offsets no case_text.

Roda o `combinado.py` em cada caso e lê os spans já refinados (`registros`), os exames com
resultado e os sítios anatômicos. Os casos do gabarito vão para `regras/mencoes.csv` (linha de
base); os demais para `silver/mencoes.csv` (treino). Formato: case_id,id,start,end,texto,tipo.
"""
from __future__ import annotations

import argparse
import csv
import logging
from pathlib import Path

from mock.comum import DADOS_MOCK, casos_gold, ler_casos

import combinado  # noqa: E402  (path ajustado por .comum)
from matching import match_text  # noqa: E402
from normalizacao.case_reader import ClinicalCase  # noqa: E402

LOGGER = logging.getLogger(__name__)
TIPOS = {"Symptom", "History", "Exam", "ExamResult", "Finding", "Diagnosis",
         "Medication", "Treatment", "Outcome", "AnatomicalSite"}
COLUNAS = ["case_id", "id", "start", "end", "texto", "tipo"]


def mencoes_das_regras(case_id: str, texto: str, recursos) -> list[tuple[int, int, str]]:
    """Spans (start, end, tipo) que as regras ancoram no texto, sem repetição."""
    caso = ClinicalCase(article_id="", age=None, case_id=case_id, case_text=texto, gender="")
    inspecao = combinado.processar_caso(caso, recursos, inspecionar=True).inspecao
    spans = []

    for reg in inspecao["registros"]:
        if not reg["descartar"] and reg["span"]:
            spans.append((*reg["span"], reg["tipo"]))

    for resultado, ref in inspecao["exames_de_resultado"]:
        if ref["span"]:
            spans.append((*ref["span"], "Exam"))
        # O valor não tem offset próprio: procura o texto bruto dentro da evidência.
        bruto = str(resultado.node.attributes.get("raw_text") or "")
        inicio = texto.lower().find(bruto.lower(), resultado.char_start, resultado.char_end) if bruto else -1
        if inicio >= 0:
            spans.append((inicio, inicio + len(bruto), "ExamResult"))

    # Sítios não guardam offset: refaz o mesmo casamento, na mesma ordem das linhas de `sitios`.
    tokens = inspecao["tokens"]
    casamentos = match_text([t.text for t in tokens], recursos.gaz_anatomia)
    for m, linha in zip(casamentos, inspecao["sitios"]):
        inicio, fim = tokens[m.start].start, tokens[m.end - 1].end
        if texto[inicio:fim] != linha["sítio"]:
            raise RuntimeError(f"{case_id}: sítio fora de ordem em {inicio}")
        if not linha["resultado"].startswith("descartado"):
            spans.append((inicio, fim, "AnatomicalSite"))

    return sorted({s for s in spans if s[2] in TIPOS and s[0] < s[1]})


def gravar(linhas: list[dict], caminho: Path) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUNAS)
        writer.writeheader()
        writer.writerows(linhas)


def gerar(saida: Path = DADOS_MOCK, limite: int | None = None) -> dict[str, int]:
    gold = casos_gold()
    recursos = combinado.carregar_recursos()
    silver, regras = [], []
    for case_id, texto in ler_casos(limite=limite):
        try:
            spans = mencoes_das_regras(case_id, texto, recursos)
        except Exception:
            LOGGER.exception("regras falharam em %s; caso ignorado", case_id)
            continue
        destino = regras if case_id in gold else silver
        for k, (inicio, fim, tipo) in enumerate(spans, 1):
            assert texto[inicio:fim], (case_id, inicio, fim)
            destino.append({"case_id": case_id, "id": f"s{k}", "start": inicio, "end": fim,
                            "texto": texto[inicio:fim], "tipo": tipo})
    gravar(silver, saida / "silver" / "mencoes.csv")
    gravar(regras, saida / "regras" / "mencoes.csv")
    return {"silver": len(silver), "regras": len(regras)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limite", type=int, help="processa só os N primeiros casos")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print(gerar(limite=args.limite))


if __name__ == "__main__":
    main()
