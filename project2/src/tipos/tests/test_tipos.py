"""Léxico, limpeza do silver e leitura dos dados na etapa 3."""
import sys
import unittest
from pathlib import Path

MODULO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULO))
import lexico  # noqa: E402
import tipos  # noqa: E402
from mock import avaliar  # noqa: E402
from mock.comum import casos_gold  # noqa: E402
from mock.silver import SILVER, ler_silver  # noqa: E402


class DadosTests(unittest.TestCase):
    def test_gabarito_tem_offsets_e_tipos_validos(self):
        for linha in tipos.ler_mencoes(tipos.GOLD):
            self.assertLess(linha["start"], linha["end"])
            self.assertIn(linha["tipo"], tipos.TIPOS)

    @unittest.skipUnless(SILVER.is_file(), "rode `entidades.py mock` para gerar o silver")
    def test_silver_nunca_tem_casos_do_gabarito(self):
        self.assertFalse({linha["case_id"] for linha in ler_silver()} & casos_gold())


class LexicoTests(unittest.TestCase):
    def test_tipo_e_codigo_de_termos_conhecidos(self):
        self.assertEqual(lexico.consultar("nausea"), lexico.Resposta("Symptom", "D009325", "termos", "termos"))
        self.assertEqual(lexico.consultar("stomach").mesh, "ANAT001")

    def test_maior_trecho_decide_o_tipo(self):
        # "flank" é AnatomicalSite, mas "abdominal pain" é maior e é o núcleo.
        self.assertEqual(lexico.consultar("right flank and lower quadrant abdominal pain").tipo, "Symptom")

    def test_tipo_sem_codigo_e_codigo_sem_tipo(self):
        self.assertEqual(lexico.consultar("6cm cystic lesion"), lexico.Resposta("Finding", "", "termos", "termos"))
        self.assertEqual(lexico.consultar("FNA"), lexico.Resposta("", "", "", ""))

    def test_categoria_do_mesh_vira_tipo(self):
        resposta = lexico.consultar("rifampin")
        self.assertEqual((resposta.tipo, resposta.fonte, resposta.categoria), ("Medication", "mesh", "drugs"))

    def test_nome_do_remedio(self):
        self.assertEqual(lexico.nome_do_remedio("OD and Pyrazinamide 500 mg"), (7, 19))
        self.assertIsNone(lexico.nome_do_remedio("a dose of 6 mg"))
        self.assertIsNone(lexico.nome_do_remedio("as hemoglobin of 6 g"))  # analito, não remédio
        self.assertIsNone(lexico.nome_do_remedio("then continued at 10 mg"))  # "at 10" é sinônimo do MeSH


class LimpezaTests(unittest.TestCase):
    def test_medication_fica_so_com_o_remedio(self):
        linhas = [{"case_id": "c", "start": 100, "end": 115, "texto": "Rifampin 600 mg", "tipo": "Medication"},
                  {"case_id": "c", "start": 200, "end": 214, "texto": "a dose of 6 mg", "tipo": "Medication"},
                  {"case_id": "c", "start": 300, "end": 306, "texto": "nausea", "tipo": "Symptom"}]
        limpas = tipos.limpar_silver(linhas)
        self.assertEqual([(x["start"], x["end"], x["texto"]) for x in limpas],
                         [(100, 108, "Rifampin"), (300, 306, "nausea")])


def _m(inicio, fim, tipo, caso="c"):
    return {"case_id": caso, "start": inicio, "end": fim, "tipo": tipo}


class AvaliarTests(unittest.TestCase):
    GOLD = [_m(0, 5, "Symptom"), _m(10, 15, "Exam"), _m(20, 25, "Exam"), _m(30, 35, "Finding")]

    def test_metricas_contadas_a_mao(self):
        pred = [_m(0, 5, "Symptom"), _m(10, 15, "Exam"), _m(20, 25, "Finding"), _m(30, 35, ""),
                _m(40, 45, "Exam")]  # a última não está no gabarito (falso positivo da etapa 2)
        m = avaliar.avaliar_tipos(pred, self.GOLD)
        self.assertEqual((m["cobertura"], m["acuracia"]), (0.75, 0.5))
        self.assertEqual(m["por_tipo"]["Exam"]["precisao"], 0.5)   # 1 acerto em 2 Exam preditos
        self.assertEqual(m["por_tipo"]["Exam"]["revocacao"], 0.5)  # 1 acerto em 2 Exam no gabarito
        self.assertEqual(m["por_tipo"]["Finding"]["f1"], 0.0)
        self.assertAlmostEqual(m["macro_f1"], (1.0 + 0.5 + 0.0) / 3)
        self.assertEqual(m["confusao"][("Finding", "")], 1)

    def test_sobreposicao_pareia_um_para_um(self):
        pred = [_m(0, 3, "Symptom"), _m(2, 5, "Symptom")]
        self.assertEqual(avaliar.avaliar_tipos(pred, self.GOLD[:1], exato=True)["acuracia"], 0.0)
        m = avaliar.avaliar_tipos(pred, self.GOLD[:1], exato=False)
        self.assertEqual((m["acuracia"], m["por_tipo"]["Symptom"]["precisao"]), (1.0, 0.5))


if __name__ == "__main__":
    unittest.main()
