"""Conversões BIO, pistas, offsets e separação do gabarito na etapa 2."""
import sys
import unittest
from pathlib import Path

MODULO = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]
for _p in (REPO, MODULO):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import entidades  # noqa: E402
from project2.src.avaliacao import avaliar  # noqa: E402
from project2.src.comum import casos_gold, tokenizar  # noqa: E402

TEXTO = ("A 44-year-old woman presented with a 3-day history of right flank and lower quadrant "
         "abdominal pain associated with nausea and constipation.")


class BioTests(unittest.TestCase):
    def test_spans_ida_e_volta_pelo_bio(self):
        spans = [(54, 99), (116, 122), (127, 139)]
        tokens = tokenizar(TEXTO)
        self.assertEqual(entidades.spans_de_bio(tokens, entidades.rotular(tokens, spans)), spans)

    def test_achatar_fica_com_o_mais_longo(self):
        self.assertEqual(entidades.achatar([(54, 99), (85, 94), (116, 122)]), [(54, 99), (116, 122)])

    def test_i_sem_b_abre_span(self):
        tokens = tokenizar(TEXTO)[:4]
        self.assertEqual(entidades.spans_de_bio(tokens, ["O", "I", "I", "O"]), [(2, 19)])

    def test_marcar_termos_pelo_mais_longo(self):
        palavras = ["lower", "quadrant", "abdominal", "pain", "and", "nausea"]
        termos = {("abdominal", "pain"), ("lower", "quadrant", "abdominal", "pain")}
        self.assertEqual(entidades.marcar_termos(palavras, termos), ["B", "I", "I", "I", "O", "O"])


class PistasTests(unittest.TestCase):
    def test_pistas_de_cada_palavra(self):
        frase = entidades.frases_do_caso(TEXTO, termos={("abdominal", "pain")})[0]
        pistas = entidades.pistas_da_palavra(frase, 0)
        for chave in ("palavra", "pre3", "suf3", "formato", "pos", "termo", "+1:palavra", "+2:pos", "-1:fora"):
            self.assertIn(chave, pistas)
        self.assertEqual(entidades._formato("CA19-9"), "Xd-d")

    def test_frases_preservam_offsets(self):
        for frase in entidades.frases_do_caso(TEXTO):
            for tok in frase:
                self.assertEqual(TEXTO[tok["start"]:tok["end"]], tok["texto"])


class SeparacaoTests(unittest.TestCase):
    def test_gabarito_fora_do_treino(self):
        gold = casos_gold()
        casos = [(c, "") for c in sorted(gold)] + [("PMC5137649_01", "")]
        mencoes = {c: [(0, 1)] for c, _ in casos}
        self.assertEqual(entidades.casos_de_treino(casos, mencoes, gold), [("PMC5137649_01", "")])


class AvaliarTests(unittest.TestCase):
    def test_exato_e_sobreposicao(self):
        gold = [("c", 0, 10), ("c", 20, 30)]
        pred = [("c", 0, 10), ("c", 22, 35), ("c", 40, 45)]
        m = avaliar.avaliar_mencoes(pred, gold)
        self.assertEqual((m["exato"]["casados"], m["sobreposicao"]["casados"]), (1, 2))
        self.assertAlmostEqual(m["sobreposicao"]["precisao"], 2 / 3)

    def test_um_gold_casa_com_um_predito(self):
        m = avaliar.avaliar_mencoes([("c", 0, 5), ("c", 5, 10)], [("c", 0, 10)])
        self.assertEqual(m["sobreposicao"]["casados"], 1)


if __name__ == "__main__":
    unittest.main()
