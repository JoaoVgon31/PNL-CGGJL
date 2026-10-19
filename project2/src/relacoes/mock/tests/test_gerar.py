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
    gerar_pares_do_caso,
    linha_negativa,
    linha_do_positivo,
)
from project2.src.relacoes.mock.gerar import dividir_casos, gerar, gravar, gravar_entidades


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

    def test_caminho_inexistente_levanta_erro_com_comando_claro(self):
        with tempfile.TemporaryDirectory() as tmp:
            caminho = Path(tmp) / "nao_existe.csv"
            with self.assertRaises(FileNotFoundError) as cm:
                carregar_mencoes("C1", caminho)
        self.assertIn("entidades.py mock", str(cm.exception))


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
        positivos, descartadas, _ = resolver_positivos(texto, mencoes, tipos, arestas)
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
        positivos, descartadas, _ = resolver_positivos(texto, mencoes, tipos, arestas)
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
        positivos, descartadas, _ = resolver_positivos(texto, mencoes, tipos, arestas)
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
        positivos, descartadas, colapsadas = resolver_positivos(texto, mencoes, tipos, arestas)
        self.assertEqual(len(positivos), 1)
        self.assertEqual(colapsadas, 1)


class TestLinhaDoPositivo(unittest.TestCase):
    def test_patient_tem_source_text_vazio(self):
        texto = "0123456789" + "dor abdominal" + "x" * 20
        destino = _mencao("s1", 10, 23, "dor abdominal", "Symptom")
        positivo = {
            "source_id": "P1", "target_id": "s1", "source_tipo": "Patient",
            "target_tipo": "Symptom", "relation": "HAS_SYMPTOM", "certainty": "asserted",
            "origem": None, "destino": destino,
        }
        linha = linha_do_positivo("C1", texto, positivo)
        self.assertEqual(linha["source_text"], "")
        self.assertEqual(linha["target_text"], "dor abdominal")
        self.assertEqual(linha["is_positive"], 1)
        self.assertEqual(linha["polarity"], "present")

    def test_nao_patient_tem_textos_e_distancia_dos_dois_lados(self):
        texto = "0123456789" + "achado" + "yy" + "figado" + "x" * 20
        origem = _mencao("f1", 10, 16, "achado", "Finding")
        destino = _mencao("a1", 18, 24, "figado", "AnatomicalSite")
        positivo = {
            "source_id": "f1", "target_id": "a1", "source_tipo": "Finding",
            "target_tipo": "AnatomicalSite", "relation": "LOCATED_IN", "certainty": "asserted",
            "origem": origem, "destino": destino,
        }
        linha = linha_do_positivo("C1", texto, positivo)
        self.assertEqual(linha["source_text"], "achado")
        self.assertEqual(linha["target_text"], "figado")
        self.assertEqual(linha["distance_chars"], 8)


class TestLinhaNegativa(unittest.TestCase):
    def test_relation_none_e_is_positive_zero(self):
        texto = "0123456789" + "dor" + "yy" + "febre" + "x" * 20
        m1 = _mencao("s1", 10, 13, "dor", "Symptom")
        m2 = _mencao("s2", 15, 20, "febre", "Symptom")
        linha = linha_negativa("C1", texto, m1, m2)
        self.assertEqual(linha["relation"], "NONE")
        self.assertEqual(linha["is_positive"], 0)
        self.assertEqual(linha["distance_chars"], 5)


class TestGerarParesDoCaso(unittest.TestCase):
    def test_gera_positivos_e_negativos_dentro_da_janela(self):
        texto = "0123456789" + "dor abdominal" + "y" * 5 + "febre" + "z" * 300
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)
            mencoes_path = raiz / "mencoes.csv"
            _escrever_csv(
                mencoes_path,
                [
                    {"case_id": "C1", "id": "s1", "start": "10", "end": "23",
                     "texto": "dor abdominal", "tipo": "Symptom"},
                    {"case_id": "C1", "id": "s2", "start": "28", "end": "33",
                     "texto": "febre", "tipo": "Symptom"},
                ],
                ["case_id", "id", "start", "end", "texto", "tipo"],
            )
            processados = raiz / "processados"
            _escrever_csv(
                processados / "C1-nodes.csv",
                [
                    {"case_id": "C1", "node_id": "P1", "type": "Patient", "label": "", "attributes": ""},
                    {"case_id": "C1", "node_id": "S1", "type": "Symptom", "label": "", "attributes": ""},
                ],
                ["case_id", "node_id", "type", "label", "attributes"],
            )
            _escrever_csv(
                processados / "C1-edges.csv",
                [
                    {"case_id": "C1", "edge_id": "e1", "source_id": "P1", "target_id": "S1",
                     "relation": "HAS_SYMPTOM",
                     "attributes": "trigger=dor; certainty=asserted; char_start=10; char_end=23"},
                ],
                ["case_id", "edge_id", "source_id", "target_id", "relation", "attributes"],
            )
            linhas, stats, mencoes = gerar_pares_do_caso("C1", texto, mencoes_path, processados)

        self.assertEqual(stats["positivos_resolvidos"], 1)
        self.assertEqual(stats["arestas_descartadas"], 0)
        self.assertEqual(len(mencoes), 2)
        relacoes = [l["relation"] for l in linhas]
        self.assertIn("HAS_SYMPTOM", relacoes)
        self.assertIn("NONE", relacoes)
        self.assertEqual(len(linhas), 2)  # 1 positivo (P1->s1) + 1 negativo (s1,s2)


class TestDividirCasos(unittest.TestCase):
    def test_particiona_em_tres_grupos_disjuntos(self):
        casos = [f"C{i}" for i in range(20)]
        splits = dividir_casos(casos, random_state=42)
        todos = splits["train"] + splits["val"] + splits["test"]
        self.assertEqual(sorted(todos), sorted(casos))
        self.assertEqual(len(set(todos)), 20)

    def test_e_deterministico(self):
        casos = [f"C{i}" for i in range(20)]
        self.assertEqual(dividir_casos(casos, random_state=42), dividir_casos(casos, random_state=42))


class TestGerarEndToEnd(unittest.TestCase):
    def test_gera_tres_csvs_e_entidades(self):
        with tempfile.TemporaryDirectory() as tmp:
            raiz = Path(tmp)

            casos_path = raiz / "case_texts.csv"
            textos = {
                f"C{i}": "0123456789" + "dor abdominal" + "y" * 5 + "febre" + "z" * 50
                for i in range(6)
            }
            _escrever_csv(
                casos_path,
                [{"case_id": cid, "case_text": texto} for cid, texto in textos.items()],
                ["case_id", "case_text"],
            )

            gold_path = raiz / "gold" / "casos.txt"
            gold_path.parent.mkdir(parents=True, exist_ok=True)
            gold_path.write_text("C5\n", encoding="utf-8")

            mencoes_path = raiz / "mencoes.csv"
            linhas_mencoes = []
            for cid in textos:
                linhas_mencoes.append(
                    {"case_id": cid, "id": "s1", "start": "10", "end": "23",
                     "texto": "dor abdominal", "tipo": "Symptom"}
                )
                linhas_mencoes.append(
                    {"case_id": cid, "id": "s2", "start": "28", "end": "33",
                     "texto": "febre", "tipo": "Symptom"}
                )
            _escrever_csv(mencoes_path, linhas_mencoes, ["case_id", "id", "start", "end", "texto", "tipo"])

            processados = raiz / "processados"
            for cid in textos:
                _escrever_csv(
                    processados / f"{cid}-nodes.csv",
                    [
                        {"case_id": cid, "node_id": "P1", "type": "Patient", "label": "", "attributes": ""},
                        {"case_id": cid, "node_id": "S1", "type": "Symptom", "label": "", "attributes": ""},
                    ],
                    ["case_id", "node_id", "type", "label", "attributes"],
                )
                _escrever_csv(
                    processados / f"{cid}-edges.csv",
                    [
                        {"case_id": cid, "edge_id": "e1", "source_id": "P1", "target_id": "S1",
                         "relation": "HAS_SYMPTOM",
                         "attributes": "trigger=dor; certainty=asserted; char_start=10; char_end=23"},
                    ],
                    ["case_id", "edge_id", "source_id", "target_id", "relation", "attributes"],
                )

            saida = raiz / "saida"

            estatisticas = gerar(
                mencoes_path=mencoes_path,
                processados=processados,
                saida=saida,
                casos_path=casos_path,
                gold_path=gold_path,
            )

            self.assertTrue((saida / "train.csv").exists())
            self.assertTrue((saida / "val.csv").exists())
            self.assertTrue((saida / "test.csv").exists())
            self.assertTrue((saida / "entidades.csv").exists())
            self.assertGreater(estatisticas["positivos_resolvidos"], 0)

            with open(saida / "entidades.csv", encoding="utf-8") as handle:
                linhas_entidades = list(csv.DictReader(handle))
            case_ids_entidades = {l["case_id"] for l in linhas_entidades}
            self.assertNotIn("C5", case_ids_entidades)  # caso de gabarito, nunca entra


if __name__ == "__main__":
    unittest.main()
