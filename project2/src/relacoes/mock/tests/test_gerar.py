# -*- coding: utf-8 -*-
"""Testes do gerador de dados mock da Etapa 4 (relacoes)."""

import csv
import tempfile
import unittest
from pathlib import Path

from project2.src.relacoes.mock.comum import casos_gold, ler_casos


def _escrever_csv(caminho: Path, linhas: list[dict], colunas: list[str]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=colunas)
        writer.writeheader()
        writer.writerows(linhas)


class TestLerCasos(unittest.TestCase):
    def test_le_pares_case_id_texto(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "casos.csv"
            _escrever_csv(
                caminho,
                [
                    {"case_id": "C1", "case_text": "texto um"},
                    {"case_id": "C2", "case_text": "texto dois"},
                ],
                ["case_id", "case_text"],
            )
            resultado = ler_casos(caminho)
        self.assertEqual(resultado, [("C1", "texto um"), ("C2", "texto dois")])

    def test_respeita_limite(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "casos.csv"
            _escrever_csv(
                caminho,
                [{"case_id": f"C{i}", "case_text": "x"} for i in range(5)],
                ["case_id", "case_text"],
            )
            resultado = ler_casos(caminho, limite=2)
        self.assertEqual(len(resultado), 2)


class TestCasosGold(unittest.TestCase):
    def test_le_um_case_id_por_linha(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "casos.txt"
            caminho.write_text("C1\nC2\n\nC3\n", encoding="utf-8")
            resultado = casos_gold(caminho)
        self.assertEqual(resultado, {"C1", "C2", "C3"})


if __name__ == "__main__":
    unittest.main()
