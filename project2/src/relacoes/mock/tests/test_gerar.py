# -*- coding: utf-8 -*-
"""Testes do gerador de dados mock da Etapa 4 (relacoes)."""

import csv
import tempfile
import unittest
from pathlib import Path

from project2.src.relacoes.mock.comum import casos_gold, ler_casos
from project2.src.relacoes.mock.gerar import (
    carregar_arestas,
    carregar_mencoes,
    carregar_tipos_dos_nos,
    parse_attributes,
)


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


class TestParseAttributes(unittest.TestCase):
    def test_divide_pares_chave_valor(self):
        bruto = "evidence_text=presented with X; trigger=presented with; certainty=asserted; char_start=10; char_end=50"
        resultado = parse_attributes(bruto)
        self.assertEqual(resultado["trigger"], "presented with")
        self.assertEqual(resultado["certainty"], "asserted")
        self.assertEqual(resultado["char_start"], "10")
        self.assertEqual(resultado["char_end"], "50")

    def test_string_vazia_retorna_dict_vazio(self):
        self.assertEqual(parse_attributes(""), {})
        self.assertEqual(parse_attributes(None), {})


class TestCarregarMencoes(unittest.TestCase):
    def test_filtra_pelo_case_id_e_converte_inteiros(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "mencoes.csv"
            _escrever_csv(
                caminho,
                [
                    {"case_id": "C1", "id": "s1", "start": "10", "end": "20",
                     "texto": "dor abdominal", "tipo": "Symptom"},
                    {"case_id": "C2", "id": "s1", "start": "5", "end": "15",
                     "texto": "febre", "tipo": "Symptom"},
                ],
                ["case_id", "id", "start", "end", "texto", "tipo"],
            )
            resultado = carregar_mencoes("C1", caminho)
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["start"], 10)
        self.assertEqual(resultado[0]["end"], 20)
        self.assertIsInstance(resultado[0]["start"], int)


class TestCarregarTiposDosNos(unittest.TestCase):
    def test_mapa_node_id_para_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            processados = Path(tmp)
            _escrever_csv(
                processados / "C1-nodes.csv",
                [
                    {"case_id": "C1", "node_id": "P1", "type": "Patient",
                     "label": "case C1", "attributes": ""},
                    {"case_id": "C1", "node_id": "S1", "type": "Symptom",
                     "label": "dor", "attributes": ""},
                ],
                ["case_id", "node_id", "type", "label", "attributes"],
            )
            resultado = carregar_tipos_dos_nos("C1", processados)
        self.assertEqual(resultado, {"P1": "Patient", "S1": "Symptom"})


class TestCarregarArestas(unittest.TestCase):
    def test_ignora_same_as_e_extrai_offsets(self):
        with tempfile.TemporaryDirectory() as tmp:
            processados = Path(tmp)
            _escrever_csv(
                processados / "C1-edges.csv",
                [
                    {"case_id": "C1", "edge_id": "e1", "source_id": "P1", "target_id": "S1",
                     "relation": "HAS_SYMPTOM",
                     "attributes": "evidence_text=x; trigger=dor; certainty=asserted; char_start=10; char_end=30"},
                    {"case_id": "C1", "edge_id": "e2", "source_id": "S1", "target_id": "C1",
                     "relation": "SAME_AS", "attributes": "strategy=exact"},
                ],
                ["case_id", "edge_id", "source_id", "target_id", "relation", "attributes"],
            )
            resultado = carregar_arestas("C1", processados)
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0]["relation"], "HAS_SYMPTOM")
        self.assertEqual(resultado[0]["char_start"], 10)
        self.assertEqual(resultado[0]["char_end"], 30)
        self.assertEqual(resultado[0]["trigger"], "dor")

    def test_descarta_aresta_sem_offset(self):
        with tempfile.TemporaryDirectory() as tmp:
            processados = Path(tmp)
            _escrever_csv(
                processados / "C1-edges.csv",
                [
                    {"case_id": "C1", "edge_id": "e1", "source_id": "P1", "target_id": "S1",
                     "relation": "HAS_SYMPTOM", "attributes": "certainty=asserted"},
                ],
                ["case_id", "edge_id", "source_id", "target_id", "relation", "attributes"],
            )
            resultado = carregar_arestas("C1", processados)
        self.assertEqual(resultado, [])


if __name__ == "__main__":
    unittest.main()
