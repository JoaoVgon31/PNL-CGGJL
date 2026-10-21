import csv
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from project2.src.termos.termos import associar, calcular_c_values, comparar, contar_caso, gerar, ler_termos, normalizar


class TermosTests(unittest.TestCase):
    def test_chave_lexical_preserva_numeros_unidades_e_sinais(self):
        self.assertEqual(normalizar("  Vitamin\u00a0B  12 "), "vitamin b 12")
        for a, b in (("Vitamin B", "Vitamin B 12"), ("Vitamin K", "Vitamin K 1"),
                     ("Type 1 diabetes mellitus", "Type 2 diabetes mellitus"),
                     ("Type 1 diabetes mellitus", "Type 1.5 diabetes mellitus"),
                     ("enzyme", "enzyme mg"), ("CD4+", "CD4-")):
            with self.subTest(a=a, b=b):
                self.assertNotEqual(normalizar(a), normalizar(b))

    def test_comparacao_nao_atribui_codigo_de_variante_numerada(self):
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d)
            termos, gaz, saida = (raiz / n for n in ("termos.csv", "gaz.csv", "comparacao.csv"))
            termos.write_text("termo,n,frequencia,pmi,c_value\nvitamin b,2,5,1,5\nvitamin k,2,4,1,4\nlactate dehydrogenase,2,3,1,3\n", encoding="utf-8")
            gaz.write_text("term,code\nVitamin B 12,D12\nVitamin K,DK\nVitamin K 1,DK1\nLactate Dehydrogenase,DL\nLactate Dehydrogenase 5,DL5\n", encoding="utf-8")
            resumo = comparar(termos, gaz, saida)
            self.assertEqual(resumo["conhecidos_mesh"], 2)
            with saida.open() as handle:
                codigos = {l["termo"]: l["codigos_mesh"] for l in csv.DictReader(handle)}
            self.assertEqual(codigos, {"vitamin b": "", "vitamin k": "DK", "lactate dehydrogenase": "DL"})

    def test_c_value_desconta_termos_aninhados_uma_vez_por_termo(self):
        a = ("blood", "cell")
        b = ("white", "blood", "cell")
        valores = calcular_c_values({a: 10, b: 4})
        self.assertEqual(valores[a], 6)
        self.assertAlmostEqual(valores[b], math.log2(3) * 4)
        # Mesmo subtermo repetido duas vezes no mesmo termo maior só conta uma vez.
        valores = calcular_c_values({("a", "a"): 8, ("a", "a", "a"): 3})
        self.assertEqual(valores[("a", "a")], 5)

    @patch("project2.src.termos.termos.etiquetar", side_effect=lambda ts: ["NOUN"] * len(ts))
    def test_nao_cruza_pontuacao_frases_ou_unidades(self, _):
        contagens, _, _, _ = contar_caso("alpha, beta. gamma! delta 6cm epsilon.")
        for termo in ("alpha beta", "beta gamma", "gamma delta", "delta epsilon"):
            self.assertNotIn((termo, 2), contagens)

    @patch("project2.src.termos.termos.etiquetar", side_effect=lambda ts: ["NOUN"] * len(ts))
    def test_exclusao_gold_pmi_posicional_e_contagens(self, _):
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d)
            corpus, gold, saida = raiz / "casos.csv", raiz / "gold.txt", raiz / "termos.csv"
            with corpus.open("w", newline="", encoding="utf-8") as handle:
                w = csv.writer(handle)
                w.writerow(["case_id", "case_text"])
                w.writerows([("PMC1_01", "alpha beta. gamma delta."),
                             ("PMC2_01", "alpha beta."), ("PMC3_01", "secret disease.")])
            gold.write_text("PMC3_01\n", encoding="utf-8")
            resumo = gerar(saida, corpus=corpus, gold=gold, freq_min=1)
            self.assertEqual(resumo["casos_processados"], 2)
            self.assertEqual(resumo["casos_gold_excluidos"], 1)
            self.assertEqual(resumo["ocorrencias_por_n"]["1"], 6)
            with saida.open() as handle:
                linhas = {l["termo"]: l for l in csv.DictReader(handle)}
            self.assertNotIn("secret disease", linhas)
            self.assertAlmostEqual(float(linhas["alpha beta"]["pmi"]), math.log2(2 * 3 / (2 * 2)), places=5)
            self.assertEqual(ler_termos(saida, limite=1), [("alpha", "beta")])
            self.assertEqual(ler_termos(saida, limite=0), [])
            self.assertTrue(saida.with_suffix(".json").is_file())

    @patch("project2.src.termos.termos.etiquetar", return_value=["VERB", "NOUN"])
    def test_filtro_pos_rejeita_verbo(self, _):
        contagens, validas, _, _ = contar_caso("developed pneumonia")
        self.assertEqual(contagens[("developed pneumonia", 2)], 1)
        self.assertEqual(validas["developed pneumonia"], 0)

    def test_falha_antes_de_gravar_sem_gold(self):
        with tempfile.TemporaryDirectory() as d:
            saida = Path(d) / "termos.csv"
            with self.assertRaises(FileNotFoundError):
                gerar(saida, gold=Path(d) / "nao-existe")
            self.assertFalse(saida.exists())

    def test_comparacao_preserva_codigos_ambiguos_e_nao_inventa_f1(self):
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d)
            termos, gaz = raiz / "termos.csv", raiz / "gaz.csv"
            termos.write_text("termo,n,frequencia,pmi,c_value\nabdominal pain,2,5,1,5\nnovel phrase,2,3,1,3\n", encoding="utf-8")
            gaz.write_text("term,code\nAbdominal Pain,D1\nabdominal pain,D2\n", encoding="utf-8")
            saida = raiz / "comparacao.csv"
            resumo = comparar(termos, gaz, saida)
            self.assertEqual(resumo["cobertura_lexical"], 0.5)
            self.assertNotIn("f1", resumo)
            with saida.open() as handle:
                linhas = list(csv.DictReader(handle))
            self.assertEqual(linhas[0]["codigos_mesh"], "D1|D2")

    def test_associacoes_pmi_conceitos_mesh_e_grafo(self):
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d)
            silver, gaz, gold = raiz / "silver.csv", raiz / "gaz.csv", raiz / "gold.txt"
            saida, prefixo = raiz / "associacoes.csv", raiz / "grafo_assoc"
            silver.write_text(
                "case_id,id,start,end,texto,tipo,mesh,polaridade\n"
                "PMC1_01,m1,0,6,cancer,Diagnosis,D009369,present\n"
                "PMC1_01,m2,10,20,metastasis,Finding,D009362,present\n"
                "PMC2_01,m1,0,6,cancer,Diagnosis,D009369,present\n"
                "PMC2_01,m2,10,20,metastasis,Finding,D009362,present\n"
                "PMC3_01,m1,0,5,fever,Symptom,D005334,present\n"
                "PMC4_01,m1,0,6,cancer,Diagnosis,D009369,present\n"
                "PMC4_01,m2,10,20,metastasis,Finding,D009362,absent\n"
                "PMC9_01,m1,0,6,cancer,Diagnosis,D009369,present\n",
                encoding="utf-8",
            )
            gaz.write_text(
                "term,code,preferred_term,category\n"
                "Cancer,D009369,Neoplasms,diseases\n"
                "Metastasis,D009362,Neoplasm Metastasis,diseases\n",
                encoding="utf-8",
            )
            gold.write_text("PMC9_01\n", encoding="utf-8")
            resumo = associar(silver=silver, gazetteer=gaz, gold=gold, saida=saida, grafo_prefixo=prefixo, freq_min=2)
            self.assertEqual(resumo["casos_processados"], 4)
            self.assertEqual(resumo["casos_gold_excluidos"], 1)
            self.assertEqual(resumo["pares_associados"], 1)
            with saida.open(encoding="utf-8") as handle:
                linhas = list(csv.DictReader(handle))
            self.assertEqual(len(linhas), 1)
            self.assertEqual(linhas[0]["codigo_a"], "D009362")
            self.assertEqual(linhas[0]["termo_a"], "Neoplasm Metastasis")
            self.assertEqual(linhas[0]["codigo_b"], "D009369")
            self.assertEqual(linhas[0]["termo_b"], "Neoplasms")
            self.assertAlmostEqual(float(linhas[0]["pmi"]), math.log2(2 * 4 / (2 * 3)), places=5)
            self.assertTrue((raiz / "grafo_assoc-nodes.csv").is_file())
            self.assertTrue((raiz / "grafo_assoc-edges.csv").is_file())

