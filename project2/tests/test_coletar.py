import csv
import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from project2.src.comum.coletar import baixar, coletar


class ColetaTests(unittest.TestCase):
    def test_retoma_resposta_truncada_sem_duplicar_o_prefixo(self):
        blob = b"a clinical case report"
        arquivo = {"size": len(blob), "checksum": "md5:" + hashlib.md5(blob).hexdigest(),
                   "links": {"self": "https://example.test/cases.parquet"}}
        class Resposta(io.BytesIO):
            pass
        def resposta(req, **kwargs):
            if req.get_header("Range"):
                self.assertEqual(req.get_header("Range"), "bytes=8-")
                r = Resposta(blob[8:])
                r.status = 206
                r.headers = {"Content-Range": f"bytes 8-{len(blob)-1}/{len(blob)}"}
                return r
            return Resposta(blob[:8])
        with tempfile.TemporaryDirectory() as d:
            destino = Path(d) / "cases.parquet"
            with patch("project2.src.comum.coletar.urlopen", side_effect=resposta), redirect_stdout(io.StringIO()):
                baixar(arquivo, destino)
            self.assertEqual(destino.read_bytes(), blob)
            self.assertFalse(destino.with_suffix(".parquet.part").exists())

    def test_servidor_ignora_range_reinicia_sem_concatenar(self):
        blob = b"a complete file"
        arquivo = {"size": len(blob), "checksum": "md5:" + hashlib.md5(blob).hexdigest(),
                   "links": {"self": "https://example.test/cases.parquet"}}
        with tempfile.TemporaryDirectory() as d:
            destino = Path(d) / "cases.parquet"
            destino.with_suffix(".parquet.part").write_bytes(blob[:5])
            with patch("project2.src.comum.coletar.urlopen", return_value=io.BytesIO(blob)), redirect_stdout(io.StringIO()):
                baixar(arquivo, destino)
            self.assertEqual(destino.read_bytes(), blob)

    def test_download_checksum_desaninhamento_exportacao_e_reuso(self):
        try:
            import duckdb
        except ImportError:
            self.skipTest("duckdb opcional não instalado")
        with tempfile.TemporaryDirectory() as d, duckdb.connect() as db:
            root = Path(d)
            casos = root / "cases.parquet"
            metadata = root / "metadata.parquet"
            db.sql("SELECT 'PMC1' AS article_id, [struct_pack(age := 44.0, case_id := 'PMC1_01', case_text := ' No fever. ', gender := 'Female')] AS cases").write_parquet(str(casos))
            db.sql("SELECT 'PMC1' AS article_id, struct_pack(title := 'A case', year := '2026') AS article_metadata").write_parquet(str(metadata))
            blobs = {"cases.parquet": casos.read_bytes(), "metadata.parquet": metadata.read_bytes(),
                     "data_dictionary.csv": b"file,field,explanation\ncases,case_text,text\n"}
            record = {"id": 123, "metadata": {"version": "test"}, "files": [
                {"key": name, "size": len(data), "checksum": "md5:" + hashlib.md5(data).hexdigest(),
                 "links": {"self": "https://example.test/" + name}} for name, data in blobs.items()]}
            def resposta(req, **kwargs):
                if "/api/records/" in req.full_url:
                    return io.BytesIO(json.dumps(record).encode())
                return io.BytesIO(blobs[req.full_url.rsplit("/", 1)[-1]])
            with patch("project2.src.comum.coletar.urlopen", side_effect=resposta) as request, redirect_stdout(io.StringIO()):
                manifesto = coletar(root / "download")
                self.assertEqual(manifesto["casos"], 1)
                self.assertEqual(request.call_count, 4)
                coletar(root / "download")
                self.assertEqual(request.call_count, 5)  # na repetição, consulta só o manifesto
            with (root / "download/csv/full/cases.csv").open() as h:
                linha = next(csv.DictReader(h))
            self.assertEqual(linha["case_text"], " No fever. ")
            self.assertEqual(linha["age"], "44.0")
            with (root / "download/csv/full/metadata.csv").open() as h:
                self.assertEqual(next(csv.DictReader(h))["title"], "A case")
            self.assertTrue((root / "download/proveniencia.json").is_file())
