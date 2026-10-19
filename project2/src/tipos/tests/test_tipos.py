"""Léxico, limpeza do silver e leitura dos dados na etapa 3."""
import sys
import unittest
from pathlib import Path
from unittest import mock as patch

import numpy as np

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
                  {"case_id": "c", "start": 300, "end": 306, "texto": "nausea", "tipo": "Symptom"},
                  # o nome que sobraria (aspirin) já é menção de outro tipo no mesmo lugar
                  {"case_id": "c", "start": 400, "end": 414, "texto": "aspirin 100 mg", "tipo": "Medication"},
                  {"case_id": "c", "start": 400, "end": 407, "texto": "aspirin", "tipo": "Treatment"}]
        limpas = tipos.limpar_silver(linhas)
        self.assertEqual([(x["start"], x["end"], x["texto"], x["tipo"]) for x in limpas],
                         [(100, 108, "Rifampin", "Medication"), (300, 306, "nausea", "Symptom"),
                          (400, 407, "aspirin", "Treatment")])


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


class ClassificadorTests(unittest.TestCase):
    TEXTO = "She presented with nausea and constipation."

    def test_contexto_marca_o_lado(self):
        mencao = {"case_id": "c", "start": 19, "end": 25, "texto": "nausea"}
        linha = tipos.pistas([mencao], {"c": self.TEXTO}).iloc[0]
        self.assertEqual(linha["mencao"], "nausea")
        self.assertEqual(linha["contexto"], "E:she E:presented E:with D:and D:constipation")

    def test_separar_nao_divide_um_caso(self):
        linhas = [{"case_id": f"c{k % 7}"} for k in range(30)]
        treino, validacao = tipos.separar(linhas)
        self.assertFalse({x["case_id"] for x in treino} & {x["case_id"] for x in validacao})
        self.assertEqual(len(treino) + len(validacao), 30)

    def test_limiar_deixa_sem_tipo(self):
        probabilidades = np.array([[0.7, 0.3], [0.45, 0.55]])
        self.assertEqual(tipos.aplicar_limiar(probabilidades, ["Exam", "Symptom"], 0.6),
                         [("Exam", 0.7), ("", 0.55)])

    def test_classificador_aprende_com_o_contexto(self):
        mencoes = [{"case_id": "c", "start": 19, "end": 25, "texto": "nausea", "tipo": "Symptom"},
                   {"case_id": "c", "start": 30, "end": 42, "texto": "constipation", "tipo": "Finding"}]
        clf = tipos.novo_classificador(1.0, None).fit(tipos.pistas(mencoes, {"c": self.TEXTO}),
                                                      [m["tipo"] for m in mencoes])
        self.assertEqual(list(clf.predict(tipos.pistas(mencoes, {"c": self.TEXTO}))), ["Symptom", "Finding"])


class TiparTests(unittest.TestCase):
    """O classificador é trocado por um falso que diz Finding (0.9) a tudo, menos a `xyzzy` (sem tipo)."""
    TEXTO = "nausea, xyzzy, rifampin and blorpus"
    MENCOES = [{"case_id": "c", "id": "m1", "start": 0, "end": 6, "texto": "nausea"},
               {"case_id": "c", "id": "m2", "start": 8, "end": 13, "texto": "xyzzy"},
               {"case_id": "c", "id": "m3", "start": 15, "end": 23, "texto": "rifampin"},
               {"case_id": "c", "id": "m4", "start": 28, "end": 35, "texto": "blorpus"}]

    @staticmethod
    def _falso(mencoes, textos):
        return [("", 0.1) if m["texto"] == "xyzzy" else ("Finding", 0.9) for m in mencoes]

    def _tipos(self, modo):
        with patch.patch.object(tipos, "classificar", side_effect=self._falso):
            return [(x["tipo"], x["fonte"]) for x in tipos.tipar(self.MENCOES, {"c": self.TEXTO}, modo)]

    def test_lexico(self):
        self.assertEqual(self._tipos("lexico"),
                         [("Symptom", "lexico"), ("", ""), ("Medication", "lexico"), ("", "")])

    def test_classificador_so_no_que_o_lexico_nao_conhece(self):
        # blorpus: o léxico não conhece, o classificador tipa; xyzzy: abaixo do limiar, segue sem tipo.
        self.assertEqual(self._tipos("lexico+classificador"),
                         [("Symptom", "lexico"), ("", ""), ("Medication", "lexico"), ("Finding", "classificador")])

    def test_ambiguas_passam_pelo_classificador(self):
        # rifampin é `drugs` no MeSH (categoria ambígua): o classificador decide.
        self.assertEqual(self._tipos("ambiguas"),
                         [("Symptom", "lexico"), ("", ""), ("Finding", "classificador"), ("Finding", "classificador")])

    def test_so_classificador(self):
        self.assertEqual(self._tipos("classificador"),
                         [("Finding", "classificador"), ("", ""), ("Finding", "classificador"),
                          ("Finding", "classificador")])

    def test_mesh_vem_sempre_do_lexico(self):
        with patch.patch.object(tipos, "classificar", side_effect=self._falso):
            linhas = tipos.tipar(self.MENCOES, {"c": self.TEXTO}, "classificador")
        self.assertEqual(linhas[0]["mesh"], "D009325")


if __name__ == "__main__":
    unittest.main()
