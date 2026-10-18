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
    resolver_entidade,
    resolver_positivos,
)


def _mencao(id_, start, end, texto, tipo):
    return {"id": id_, "start": start, "end": end, "texto": texto, "tipo": tipo}


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


class TestResolverEntidade(unittest.TestCase):
    def test_unica_candidata_na_janela(self):
        mencoes = [_mencao("s1", 10, 20, "dor", "Symptom")]
        resultado = resolver_entidade(mencoes, "Symptom", 0, 30, "dor", "texto qualquer com dor aqui")
        self.assertEqual(resultado["id"], "s1")

    def test_nenhuma_candidata_retorna_none(self):
        mencoes = [_mencao("s1", 10, 20, "dor", "Symptom")]
        resultado = resolver_entidade(mencoes, "AnatomicalSite", 0, 30, "x", "texto")
        self.assertIsNone(resultado)

    def test_candidata_fora_da_janela_e_ignorada(self):
        mencoes = [_mencao("s1", 500, 510, "dor", "Symptom")]
        resultado = resolver_entidade(mencoes, "Symptom", 0, 30, "x", "texto" * 200)
        self.assertIsNone(resultado)

    def test_desambigua_pela_proximidade_do_trigger(self):
        texto = "a" * 10 + "febre" + "b" * 10 + "palido" + "c" * 10
        mencoes = [
            _mencao("s1", 10, 15, "febre", "Symptom"),
            _mencao("s2", 25, 31, "palido", "Symptom"),
        ]
        resultado = resolver_entidade(mencoes, "Symptom", 0, len(texto), "palido", texto)
        self.assertEqual(resultado["id"], "s2")


class TestResolverPositivos(unittest.TestCase):
    def test_relacao_com_patient_nao_precisa_de_span_na_origem(self):
        texto = "0123456789" + "dor abdominal" + "x" * 20
        mencoes = [_mencao("s1", 10, 23, "dor abdominal", "Symptom")]
        tipos = {"P1": "Patient", "S1": "Symptom"}
        arestas = [
            {"source_id": "P1", "target_id": "S1", "relation": "HAS_SYMPTOM",
             "certainty": "asserted", "char_start": 0, "char_end": 23, "trigger": "dor"},
        ]
        positivos, descartadas = resolver_positivos(texto, mencoes, tipos, arestas)
        self.assertEqual(len(positivos), 1)
        self.assertEqual(positivos[0]["source_id"], "P1")
        self.assertEqual(positivos[0]["target_id"], "s1")
        self.assertIsNone(positivos[0]["origem"])
        self.assertEqual(positivos[0]["destino"]["id"], "s1")
        self.assertEqual(descartadas, 0)

    def test_relacao_sem_patient_resolve_os_dois_lados(self):
        texto = "0123456789" + "achado" + "yy" + "figado" + "x" * 20
        mencoes = [
            _mencao("f1", 10, 16, "achado", "Finding"),
            _mencao("a1", 18, 24, "figado", "AnatomicalSite"),
        ]
        tipos = {"F1": "Finding", "A1": "AnatomicalSite"}
        arestas = [
            {"source_id": "F1", "target_id": "A1", "relation": "LOCATED_IN",
             "certainty": "asserted", "char_start": 10, "char_end": 24, "trigger": "figado"},
        ]
        positivos, descartadas = resolver_positivos(texto, mencoes, tipos, arestas)
        self.assertEqual(len(positivos), 1)
        self.assertEqual(positivos[0]["source_id"], "f1")
        self.assertEqual(positivos[0]["target_id"], "a1")
        self.assertEqual(descartadas, 0)

    def test_descarta_quando_nenhuma_candidata(self):
        texto = "texto sem nada relevante" * 5
        mencoes = []
        tipos = {"P1": "Patient", "S1": "Symptom"}
        arestas = [
            {"source_id": "P1", "target_id": "S1", "relation": "HAS_SYMPTOM",
             "certainty": "asserted", "char_start": 0, "char_end": 20, "trigger": "x"},
        ]
        positivos, descartadas = resolver_positivos(texto, mencoes, tipos, arestas)
        self.assertEqual(positivos, [])
        self.assertEqual(descartadas, 1)

    def test_deduplica_pares_repetidos(self):
        texto = "0123456789" + "dor" + "x" * 20
        mencoes = [_mencao("s1", 10, 13, "dor", "Symptom")]
        tipos = {"P1": "Patient", "S1": "Symptom"}
        arestas = [
            {"source_id": "P1", "target_id": "S1", "relation": "HAS_SYMPTOM",
             "certainty": "asserted", "char_start": 0, "char_end": 13, "trigger": "dor"},
            {"source_id": "P1", "target_id": "S1", "relation": "HAS_SYMPTOM",
             "certainty": "hedged", "char_start": 0, "char_end": 13, "trigger": "dor"},
        ]
        positivos, _ = resolver_positivos(texto, mencoes, tipos, arestas)
        self.assertEqual(len(positivos), 1)


if __name__ == "__main__":
    unittest.main()
