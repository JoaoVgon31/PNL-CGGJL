import csv
import tempfile
import unittest
from pathlib import Path

from project2.src.comum import casos_gold, dividir_frases, etiquetar, iter_casos, ler_casos, tokenizar


class ComumTests(unittest.TestCase):
    def test_offsets_clinicos_e_unicode(self):
        texto = "She had nausea. 12,476.5ng/ml; 6cm; café.\nNo fever!"
        tokens = tokenizar(texto)
        self.assertIn("12,476.5", [t.text for t in tokens])
        self.assertIn("ng/ml", [t.text for t in tokens])
        for t in tokens:
            self.assertEqual(texto[t.start:t.end], t.text)
        for s in dividir_frases(texto):
            self.assertEqual(texto[s.start:s.end], s.text)

    def test_frase_decimal_mantem_contrato_p1(self):
        texto = "Level 3.5 mg/dL. No fever!"
        self.assertEqual([s.text for s in dividir_frases(texto)], ["Level 3.5 mg/dL", " No fever"])

    def test_hmm_recebe_sublista_com_indices_globais(self):
        tokens = tokenizar("She had nausea. No fever.")
        tags = etiquetar(tokens[4:])
        self.assertEqual(len(tags), len(tokens[4:]))
        self.assertIn("NOUN", tags)
        self.assertEqual(etiquetar([]), [])

    def test_csv_multilinha_limite_e_duplicatas(self):
        with tempfile.TemporaryDirectory() as d:
            arquivo = Path(d) / "casos.csv"
            with arquivo.open("w", newline="", encoding="utf-8") as handle:
                w = csv.writer(handle)
                w.writerow(["case_id", "case_text"])
                w.writerows([("PMC1_01", " A, B.\nCafé! "), ("PMC2_01", "second"), ("PMC1_01", "duplicate")])
            self.assertEqual(ler_casos(arquivo, 1), [("PMC1_01", " A, B.\nCafé! ")])
            self.assertEqual(list(iter_casos(arquivo, 0)), [])
            with self.assertRaises(ValueError):
                list(iter_casos(arquivo))
            with self.assertRaises(ValueError):
                ler_casos(arquivo, -1)

    def test_gold_ausente_vazio_invalido_e_comentarios(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "gold.txt"
            with self.assertRaises(FileNotFoundError):
                casos_gold(path)
            path.write_text("# Lista da equipe\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                casos_gold(path)
            path.write_text("PMC1_01\nPMC2_01\nPMC1_01\n# comentário\n", encoding="utf-8")
            self.assertEqual(casos_gold(path), {"PMC1_01", "PMC2_01"})

    def test_leitura_parquet_plano_e_aninhado(self):
        try:
            import duckdb
        except ImportError:
            self.skipTest("duckdb opcional não instalado")
        with tempfile.TemporaryDirectory() as d, duckdb.connect() as db:
            for nome, query in (("plano", "SELECT 'PMC1_01' AS case_id, ' A. ' AS case_text"),
                                ("aninhado", "SELECT 'PMC1' AS article_id, [struct_pack(age := 44.0, case_id := 'PMC1_01', case_text := ' A. ', gender := 'Female')] AS cases")):
                path = Path(d) / f"{nome}.parquet"
                db.sql(query).write_parquet(str(path))
                self.assertEqual(ler_casos(path), [("PMC1_01", " A. ")])
