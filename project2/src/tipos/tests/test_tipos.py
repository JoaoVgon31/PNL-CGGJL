"""Léxico, limpeza do silver e leitura dos dados na etapa 3."""
import sys
import unittest
from pathlib import Path

MODULO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(MODULO))
import lexico  # noqa: E402
import tipos  # noqa: E402
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


if __name__ == "__main__":
    unittest.main()
