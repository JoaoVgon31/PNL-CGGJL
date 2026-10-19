"""Coleta do MultiCaRe seguindo to-kg/notebooks/01_data_preparation.ipynb da disciplina."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from http.client import IncompleteRead
from pathlib import Path
from urllib.request import Request, urlopen

from .corpus import REPO, iter_registros

CONCEITO = "10079369"
ARQUIVOS = ("cases.parquet", "metadata.parquet", "data_dictionary.csv")
FONTE = "https://github.com/santanche/nlp2learn/blob/main/to-kg/notebooks/01_data_preparation.ipynb"


def baixar(arquivo: dict, destino: Path):
    esperado = arquivo["size"]
    checksum = arquivo.get("checksum", "")
    if checksum and not checksum.startswith("md5:"):
        raise ValueError(f"Checksum não suportado: {checksum}")
    def confere(path):
        if not path.is_file() or path.stat().st_size != esperado:
            return False
        if not checksum:
            return True
        digest = hashlib.md5()
        with path.open("rb") as handle:
            for bloco in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(bloco)
        return digest.hexdigest() == checksum.split(":", 1)[1]
    if confere(destino):
        print(f"{destino.name}: já disponível e validado", flush=True)
        return
    temporario = destino.with_suffix(destino.suffix + ".part")
    for tentativa in range(1, 4):
        parcial = temporario.stat().st_size if temporario.exists() else 0
        inicio = parcial if 0 < parcial < esperado else 0
        headers = {"User-Agent": "PNL-CGGJL-project2/1.0"}
        if inicio:
            headers["Range"] = f"bytes={inicio}-"
        print(f"{destino.name}: tentativa {tentativa}, {inicio}/{esperado} bytes disponíveis", flush=True)
        req = Request(arquivo["links"]["self"], headers=headers)
        try:
            with urlopen(req, timeout=120) as resposta:
                retoma = getattr(resposta, "status", 200) == 206
                if retoma:
                    intervalo = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", resposta.headers.get("Content-Range", ""))
                    if not intervalo or int(intervalo[1]) != inicio or int(intervalo[3]) != esperado:
                        raise ValueError("Content-Range incompatível com o arquivo esperado")
                # Um servidor que ignora Range exige reinício; jamais concatena uma resposta 200.
                modo = "ab" if retoma and inicio else "wb"
                with temporario.open(modo) as handle:
                    anterior = handle.tell() // (32 * 1024 * 1024)
                    while bloco := resposta.read(1024 * 1024):
                        handle.write(bloco)
                        atual = handle.tell() // (32 * 1024 * 1024)
                        if atual > anterior:
                            print(f"{destino.name}: {handle.tell()}/{esperado} bytes", flush=True)
                            anterior = atual
        except (OSError, IncompleteRead) as error:
            if tentativa == 3:
                raise
            print(f"Transferência interrompida: {error}; tentando retomar", file=sys.stderr, flush=True)
            continue
        if confere(temporario):
            temporario.replace(destino)
            print(f"{destino.name}: {esperado} bytes, checksum validado", flush=True)
            return
    obtido = temporario.stat().st_size if temporario.exists() else 0
    raise ValueError(f"Tamanho/checksum inválido após 3 tentativas: {temporario} ({obtido}/{esperado} bytes)")


def coletar(destino: Path, registro: str = "latest") -> dict:
    try:
        import duckdb
    except ImportError as error:
        raise RuntimeError("Instale project2/src/comum/requirements.txt antes de coletar") from error
    endpoint = (f"https://zenodo.org/api/records/{CONCEITO}/versions/latest" if registro == "latest"
                else f"https://zenodo.org/api/records/{int(registro)}")
    with urlopen(Request(endpoint, headers={"User-Agent": "PNL-CGGJL-project2/1.0"}), timeout=60) as resposta:
        record = json.load(resposta)
    raw = destino / "raw" / str(record["id"])
    raw.mkdir(parents=True, exist_ok=True)
    arquivos = {f["key"]: f for f in record["files"]}
    (raw / "registro.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for nome in ARQUIVOS:
        baixar(arquivos[nome], raw / nome)
    full = destino / "csv" / "full"
    full.mkdir(parents=True, exist_ok=True)
    # A versão publicada tem uma lista de casos dentro de cada artigo. iter_registros desaninha.
    contagem = 0
    parcial = full / "cases.csv.part"
    with parcial.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["article_id", "age", "case_id", "case_text", "gender"])
        writer.writeheader()
        for linha in iter_registros(raw / "cases.parquet"):
            writer.writerow({k: linha.get(k, "") for k in writer.fieldnames})
            contagem += 1
    parcial.replace(full / "cases.csv")
    with duckdb.connect() as db:
        cursor = db.execute("SELECT article_id, article_metadata.* FROM read_parquet(?)", [str(raw / "metadata.parquet")])
        with (full / "metadata.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow([c[0] for c in cursor.description])
            while lote := cursor.fetchmany(512):
                writer.writerows(lote)
    (full / "data_dictionary.csv").write_bytes((raw / "data_dictionary.csv").read_bytes())
    manifesto = {"record_id": record["id"], "version": record["metadata"].get("version"),
                 "endpoint": endpoint, "tutorial": FONTE, "casos": contagem,
                 "arquivos": [{k: arquivos[n][k] for k in ("key", "size", "checksum")} for n in ARQUIVOS]}
    (destino / "proveniencia.json").write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifesto


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destino", type=Path, default=REPO / "project2/data/corpus")
    parser.add_argument("--registro", default="latest", help="ID Zenodo para reproduzir uma versão, ou latest")
    args = parser.parse_args()
    try:
        print(json.dumps(coletar(args.destino, args.registro), ensure_ascii=False, indent=2))
    except (ValueError, RuntimeError, OSError) as error:
        parser.exit(2, f"Erro na coleta: {error}\n")


if __name__ == "__main__":
    main()
