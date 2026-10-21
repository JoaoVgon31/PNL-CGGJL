# -*- coding: utf-8 -*-
"""Testes unitários para project2/src/dados/silver.py e project2/src/avaliacao/avaliar.py (#29)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from project2.src.avaliacao import (
    avaliar_grafo,
    avaliar_mencoes,
    avaliar_relacoes,
    avaliar_tipos,
)
from project2.src.comum import casos_gold, ler_casos
from project2.src.dados.silver import GOLD_PADRAO, REGRAS, SILVER, ler_silver


class SilverGoldTests(unittest.TestCase):
    def test_silver_exclui_casos_gold(self):
        gold = casos_gold(GOLD_PADRAO)
        linhas = ler_silver(SILVER, GOLD_PADRAO)
        self.assertGreater(len(linhas), 0)
        self.assertFalse({l["case_id"] for l in linhas} & gold)

    def test_alinhamento_offsets_silver_e_regras(self):
        textos = dict(ler_casos())
        for caminho in (SILVER, REGRAS):
            for linha in ler_silver(caminho, gold_path=GOLD_PADRAO) if caminho == SILVER else []:
                self.assertEqual(
                    textos[linha["case_id"]][linha["start"]:linha["end"]],
                    linha["texto"],
                )


class AvaliarTests(unittest.TestCase):
    def test_avaliar_mencoes_exato_e_sobreposicao(self):
        gold = [("c1", 0, 10), ("c1", 20, 30)]
        pred = [("c1", 0, 10), ("c1", 22, 35), ("c1", 40, 45)]
        res = avaliar_mencoes(pred, gold)
        self.assertEqual(res["exato"]["casados"], 1)
        self.assertEqual(res["sobreposicao"]["casados"], 2)

    def test_avaliar_tipos_e_polaridade(self):
        gold = [
            {"case_id": "c1", "start": 0, "end": 5, "tipo": "Symptom", "polaridade": "present"},
            {"case_id": "c1", "start": 10, "end": 15, "tipo": "Finding", "polaridade": "absent"},
        ]
        pred = [
            {"case_id": "c1", "start": 0, "end": 5, "tipo": "Symptom", "polaridade": "present"},
            {"case_id": "c1", "start": 10, "end": 15, "tipo": "Finding", "polaridade": "absent"},
        ]
        res = avaliar_tipos(pred, gold, exato=True)
        self.assertEqual(res["acuracia"], 1.0)
        self.assertEqual(res["acuracia_polaridade"], 1.0)
        self.assertEqual(res["f1_absent"], 1.0)

    def test_avaliar_relacoes_por_spans_ids_diferentes(self):
        gold_m = [
            {"case_id": "c1", "id": "g1", "start": 10, "end": 20, "tipo": "Exam"},
            {"case_id": "c1", "id": "g2", "start": 30, "end": 40, "tipo": "ExamResult"},
        ]
        pred_m = [
            {"case_id": "c1", "id": "m99", "start": 10, "end": 20, "tipo": "Exam"},
            {"case_id": "c1", "id": "m100", "start": 32, "end": 38, "tipo": "ExamResult"},
        ]
        gold_r = [
            {"case_id": "c1", "origem": "P1", "destino": "g1", "relacao": "UNDERWENT_EXAM"},
            {"case_id": "c1", "origem": "g1", "destino": "g2", "relacao": "HAS_RESULT"},
        ]
        pred_r = [
            {"case_id": "c1", "origem": "P1", "destino": "m99", "relacao": "UNDERWENT_EXAM"},
            {"case_id": "c1", "origem": "m99", "destino": "m100", "relacao": "HAS_RESULT"},
        ]
        exato = avaliar_relacoes(pred_r, gold_r, pred_m, gold_m, exato=True)
        sobrep = avaliar_relacoes(pred_r, gold_r, pred_m, gold_m, exato=False)
        self.assertEqual(exato["casados"], 1)
        self.assertEqual(sobrep["casados"], 2)
        self.assertEqual(sobrep["f1"], 1.0)

    def test_avaliar_grafo_detecta_duplicados_mesh(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            (pasta / "c1-nodes.csv").write_text(
                "case_id,node_id,type,label,attributes\n"
                "c1,P1,Patient,patient,\n"
                "c1,N1,Symptom,fever,\n"
                "c1,N2,Symptom,pyrexia,\n"
                "c1,C1,Concept,Fever,code=D005334\n",
                encoding="utf-8",
            )
            (pasta / "c1-edges.csv").write_text(
                "case_id,edge_id,source_id,target_id,relation,attributes\n"
                "c1,E1,P1,N1,HAS_SYMPTOM,\n"
                "c1,E2,N1,C1,SAME_AS,\n"
                "c1,E3,N2,C1,SAME_AS,\n",
                encoding="utf-8",
            )
            res = avaliar_grafo(pasta)
            self.assertEqual(res["n_casos"], 1)
            self.assertEqual(res["nos_clinicos"], 2)
            self.assertEqual(res["nos_clinicos_com_mesh"], 2)
            self.assertEqual(res["pct_nos_com_mesh"], 1.0)
            self.assertEqual(res["nos_duplicados_mesmo_mesh"], 1)


if __name__ == "__main__":
    unittest.main()
