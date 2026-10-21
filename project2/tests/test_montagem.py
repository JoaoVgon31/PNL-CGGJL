import csv
import json
import tempfile
import unittest
from pathlib import Path

from project2.src.montagem.montagem import montar, montar_caso, normalizar_rotulo
from project1.tools.graph_csv import read_edges_csv


def mencao(texto, trecho, id, tipo="Finding", mesh="", polaridade="present", inicio=0):
    start = texto.index(trecho, inicio)
    return {"case_id": "PMC1_01", "id": id, "texto": trecho, "start": start,
            "end": start + len(trecho), "tipo": tipo, "mesh": mesh, "polaridade": polaridade}


class MontagemTests(unittest.TestCase):
    def test_faixas_e_hifen_preservam_a_medida_inteira(self):
        for medida in ("0.2-0.8 cm", "0.2–0.8 cm", "0.2—0.8 cm", "0.2−0.8 cm", "0.2 cm - 0.8 cm", "7-mm", ".2-.8 cm"):
            with self.subTest(medida=medida):
                self.assertEqual(normalizar_rotulo(medida + " ulcers"), ("ulcers", [medida]))
        # Unidades não suportadas ou números negativos não são removidos parcialmente.
        for texto in ("0.2-0.8 kg ulcers", "-0.8 cm ulcers"):
            with self.subTest(texto=texto):
                self.assertEqual(normalizar_rotulo(texto), (texto, []))

    def test_evidencia_e_offsets_sobrevivem_a_gravacao_e_leitura_csv(self):
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d)
            texto = 'CT; p=0.05 showed a cyst, "café"; dose=x\\y.\n'
            corpus, ms, rs = (raiz / n for n in ("casos.csv", "mencoes.csv", "relacoes.csv"))
            with corpus.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["case_id", "case_text"])
                writer.writerow(["PMC1_01", texto])
            # A menção do achado inclui toda a evidência restante, com aspas, vírgula e quebra de linha.
            inicio = texto.index("cyst")
            with ms.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(["case_id", "id", "start", "end", "texto", "tipo", "mesh", "polaridade"])
                writer.writerow(["PMC1_01", "m1", 0, 2, "CT", "Exam", "", "present"])
                writer.writerow(["PMC1_01", "m2", inicio, len(texto), texto[inicio:], "Finding", "", "present"])
            rs.write_text("case_id,origem,destino,relacao\nPMC1_01,m1,m2,REVEALS\n", encoding="utf-8")
            montar(ms, rs, corpus, raiz / "grafo")
            attrs = read_edges_csv(raiz / "grafo/PMC1_01-edges.csv")[0]["attributes"]
            self.assertEqual(attrs["evidence_text"], texto)
            self.assertEqual(texto[int(attrs["char_start"]):int(attrs["char_end"])], texto)
            self.assertNotIn("p", attrs)
            self.assertNotIn("dose", attrs)

    def test_dimensoes_com_unidades_repetidas(self):
        rotulo, medidas = normalizar_rotulo("9.5cm x 4.5cm x 2.0cm cystic lesion")
        self.assertEqual(rotulo, "cystic lesion")
        self.assertEqual(medidas, ["9.5cm x 4.5cm x 2.0cm"])

    def test_mescla_equivalentes_preserva_negacao_e_medida(self):
        texto = "6cm cyst. cyst. No cyst."
        ms = [mencao(texto, "6cm cyst", "m1", mesh="D1"),
              mencao(texto, "cyst", "m2", mesh="D1", inicio=10),
              mencao(texto, "cyst", "m3", mesh="D1", polaridade="absent", inicio=18)]
        rs = [{"origem": "P1", "destino": m, "relacao": "HAS_FINDING"} for m in ("m1", "m2", "m3")]
        nodes, edges = montar_caso("PMC1_01", texto, ms, rs)
        findings = [n for n in nodes if n["type"] == "Finding"]
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0]["label"], "cyst")
        self.assertEqual(findings[0]["attributes"]["size"], "6cm")
        self.assertEqual(findings[0]["attributes"]["mentions"], "m1|m2")
        self.assertEqual(len([n for n in nodes if n["type"] == "Concept"]), 1)
        self.assertEqual(len([e for e in edges if e["relation"] == "HAS_FINDING"]), 2)

    def test_codigo_mesmo_tipo_junta_rotulos_distintos(self):
        texto = "CT and computed tomography"
        ms = [mencao(texto, "CT", "m1", "Exam", "D1"),
              mencao(texto, "computed tomography", "m2", "Exam", "D1")]
        nodes, _ = montar_caso("PMC1_01", texto, ms, [])
        self.assertEqual(len([n for n in nodes if n["type"] == "Exam"]), 1)

    def test_rotulo_ambiguo_sem_mesh_nao_funde_conceitos_conflitantes(self):
        texto = "cyst cyst cyst"
        ms = [mencao(texto, "cyst", "m1", mesh="D1"),
              mencao(texto, "cyst", "m2", mesh="D2", inicio=5),
              mencao(texto, "cyst", "m3", inicio=10)]
        nodes, _ = montar_caso("PMC1_01", texto, ms, [])
        self.assertEqual(len([n for n in nodes if n["type"] == "Finding"]), 3)

    def test_rotulo_nao_mescla_tipos_diferentes(self):
        texto = "pain pain"
        nodes, _ = montar_caso("PMC1_01", texto, [mencao(texto, "pain", "m1", "Symptom"),
                                               mencao(texto, "pain", "m2", "Diagnosis", inicio=5)], [])
        self.assertEqual(len(nodes), 3)

    def test_rejeita_span_id_domino_e_confianca_invalidos(self):
        texto = "nausea"
        m = mencao(texto, "nausea", "m1", "Symptom")
        with self.assertRaises(ValueError):
            montar_caso("PMC1_01", texto, [{**m, "end": 2}], [])
        with self.assertRaises(ValueError):
            montar_caso("PMC1_01", texto, [m, m], [])
        for r in ({"origem": "P1", "destino": "missing", "relacao": "HAS_SYMPTOM"},
                  {"origem": "P1", "destino": "m1", "relacao": "UNDERWENT_EXAM"},
                  {"origem": "P1", "destino": "m1", "relacao": "HAS_SYMPTOM", "confianca": "nan"}):
            with self.assertRaises(ValueError):
                montar_caso("PMC1_01", texto, [m], [r])

    def test_caso_sem_mencoes_ainda_tem_paciente(self):
        nodes, edges = montar_caso("PMC1_01", "healthy", [], [], {"age": "44", "gender": "Female"})
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["attributes"]["age"], "44")
        self.assertEqual(edges, [])

    def test_csv_json_e_visualizador_integrados(self):
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d)
            corpus = raiz / "casos.csv"
            corpus.write_text("case_id,case_text\nPMC1_01,She had nausea.\n", encoding="utf-8")
            ms = raiz / "mencoes.csv"
            ms.write_text("case_id,id,start,end,texto,tipo,mesh,polaridade\nPMC1_01,m1,8,14,nausea,Symptom,D009325,present\n", encoding="utf-8")
            rs = raiz / "relacoes.csv"
            rs.write_text("case_id,origem,destino,relacao\nPMC1_01,P1,m1,HAS_SYMPTOM\n", encoding="utf-8")
            resumo = montar(ms, rs, corpus, raiz / "grafo", visualizador=raiz / "site")
            self.assertEqual((resumo["nos"], resumo["arestas"]), (3, 2))
            with (raiz / "grafo/PMC1_01-nodes.csv").open() as handle:
                self.assertEqual(len(list(csv.DictReader(handle))), 3)
            payload = json.loads((raiz / "site/data/PMC1_01.json").read_text())
            self.assertEqual(len(payload["graphs"]["combinado"]["edges"]), 2)
            clinical = payload["graphs"]["combinado"]["edges"][0]["attributes"]
            self.assertEqual("She had nausea."[clinical["char_start"]:clinical["char_end"]], clinical["evidence_text"])
            self.assertTrue((raiz / "site/vendor/cytoscape.min.js").is_file())

    def test_ponte_explicita_para_etapa3_sem_polaridade_e_sem_tipo(self):
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d)
            corpus = raiz / "casos.csv"
            corpus.write_text("case_id,case_text\nPMC1_01,No nausea and pain.\n", encoding="utf-8")
            ms = raiz / "mencoes.csv"
            ms.write_text("case_id,id,start,end,texto,tipo,mesh\nPMC1_01,m1,3,9,nausea,Symptom,D009325\nPMC1_01,m2,14,18,pain,,\n", encoding="utf-8")
            rs = raiz / "relacoes.csv"
            rs.write_text("case_id,origem,destino,relacao\nPMC1_01,P1,m1,HAS_SYMPTOM\nPMC1_01,P1,m2,HAS_SYMPTOM\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                montar(ms, rs, corpus, raiz / "grafo")
            self.assertFalse((raiz / "grafo").exists())
            resumo = montar(ms, rs, corpus, raiz / "grafo", visualizador=raiz / "site",
                            polaridade_regras=True, ignorar_sem_tipo=True)
            self.assertEqual(resumo["mencoes_sem_tipo_omitidas"], 1)
            self.assertEqual(resumo["relacoes_com_ponta_sem_tipo_omitidas"], 1)
            payload = json.loads((raiz / "site/data/PMC1_01.json").read_text())
            nodes = payload["graphs"]["combinado"]["nodes"]
            symptom = next(n for n in nodes if n["type"] == "Symptom")
            self.assertEqual(symptom["attributes"]["polarity"], "absent")

    def test_visualizador_duas_abas_p1_e_p2(self):
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d)
            corpus = raiz / "casos.csv"
            corpus.write_text("case_id,case_text\nPMC1_01,She had nausea.\n", encoding="utf-8")
            ms = raiz / "mencoes.csv"
            ms.write_text("case_id,id,start,end,texto,tipo,mesh,polaridade\nPMC1_01,m1,8,14,nausea,Symptom,D009325,present\n", encoding="utf-8")
            rs = raiz / "relacoes.csv"
            rs.write_text("case_id,origem,destino,relacao\nPMC1_01,P1,m1,HAS_SYMPTOM\n", encoding="utf-8")
            
            p1_dir = raiz / "p1_processed"
            p1_dir.mkdir()
            (p1_dir / "PMC1_01-nodes.csv").write_text(
                "case_id,node_id,type,label,attributes\nPMC1_01,P1,Patient,case PMC1_01,\nPMC1_01,S1,Symptom,nausea,polarity=present\n",
                encoding="utf-8"
            )
            (p1_dir / "PMC1_01-edges.csv").write_text(
                "case_id,edge_id,source_id,target_id,relation,attributes\nPMC1_01,e1,P1,S1,HAS_SYMPTOM,char_start=8; char_end=14\n",
                encoding="utf-8"
            )
            
            montar(ms, rs, corpus, raiz / "grafo", visualizador=raiz / "site", p1_grafos=p1_dir)
            payload = json.loads((raiz / "site/data/PMC1_01.json").read_text(encoding="utf-8"))
            self.assertIn("projeto1", payload["graphs"])
            self.assertIn("projeto2", payload["graphs"])
            self.assertIn("combinado", payload["graphs"])
            self.assertEqual(len(payload["graphs"]["projeto1"]["nodes"]), 2)
            self.assertEqual(len(payload["graphs"]["projeto1"]["edges"]), 1)
            self.assertEqual(len(payload["graphs"]["projeto2"]["nodes"]), 3)
            manifest = json.loads((raiz / "site/data/manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["cases"][0]["graphs"], ["projeto1", "projeto2"])
