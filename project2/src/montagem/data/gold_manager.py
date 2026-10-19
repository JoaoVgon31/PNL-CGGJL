# -*- coding: utf-8 -*-
"""Gerenciamento, validacao e consolidacao do Gabarito Ouro (Gold Standard).

Este modulo fornece:
1. Geracao de starter packs (pre-anotacoes baseadas em silver) para os casos de teste.
2. Validacao rigorosa das anotacoes manuais (offsets de caracteres, tipos clinicos,
   integridade referencial de relacoes e polaridade).
3. Consolidacao dos casos individuais em gold_entidades.csv e gold_relacoes.csv.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CASE_TEXTS = REPO_ROOT / "project1" / "data" / "case_texts.csv"
DEFAULT_SPLITS_PATH = REPO_ROOT / "project2" / "data" / "splits.json"
DEFAULT_SILVER_DIR = REPO_ROOT / "project2" / "data" / "silver"
DEFAULT_GOLD_DIR = REPO_ROOT / "project2" / "data" / "gold"

VALID_TYPES = {
    "Patient",
    "Symptom",
    "Exam",
    "ExamResult",
    "Finding",
    "Diagnosis",
    "AnatomicalSite",
    "Medication",
    "Treatment",
    "Outcome",
    "Concept",
}

VALID_RELATIONS = {
    "HAS_SYMPTOM",
    "UNDERWENT_EXAM",
    "HAS_RESULT",
    "REVEALS",
    "LOCATED_IN",
    "DIAGNOSED_WITH",
    "TREATED_WITH",
    "HAS_FINDING",
    "HAS_OUTCOME",
    "SUPPORTS",
    "REVISES",
    "SAME_AS",
}

VALID_POLARITIES = {"present", "absent"}
VALID_CERTAINTIES = {"asserted", "hedged", "conditional"}


class GoldValidationError(Exception):
    """Excecao para falhas estruturais ou de alinhamento no gabarito ouro."""
    pass


def validate_case_annotation(
    case_id: str,
    df_entities: pd.DataFrame,
    df_relations: pd.DataFrame,
    case_text: str,
) -> Dict[str, Any]:
    """Valida rigorosamente os CSVs de entidades e relacoes de um caso clinico.

    Verifica:
      1. Presenca de todas as colunas obrigatorias.
      2. Alinhamento de offsets: case_text[char_start:char_end] == texto.
      3. char_start < char_end e valores inteiros positivos.
      4. Validade dos tipos clinicos (quando preenchidos).
      5. Integridade referencial: source e target de cada relacao devem existir em ent_id.
      6. Validade de relacao, polaridade e certeza.
    """
    errors: List[str] = []
    warnings: List[str] = []

    # Validacao de colunas de entidades
    required_ent_cols = {"case_id", "ent_id", "char_start", "char_end", "texto"}
    missing_ent_cols = required_ent_cols - set(df_entities.columns)
    if missing_ent_cols:
        errors.append(f"Colunas obrigatorias ausentes em entidades: {missing_ent_cols}")
        return {"status": "error", "errors": errors, "warnings": warnings}

    # Validacao de colunas de relacoes
    required_rel_cols = {"case_id", "source", "target", "relation"}
    missing_rel_cols = required_rel_cols - set(df_relations.columns)
    if missing_rel_cols:
        errors.append(f"Colunas obrigatorias ausentes em relacoes: {missing_rel_cols}")
        return {"status": "error", "errors": errors, "warnings": warnings}

    ent_ids_found: Set[str] = set()

    # Checagem de entidades linha por linha
    for row_idx, row in df_entities.iterrows():
        eid = str(row["ent_id"]).strip()
        ent_ids_found.add(eid)

        try:
            start = int(row["char_start"])
            end = int(row["char_end"])
        except (ValueError, TypeError):
            errors.append(f"Linha {row_idx}: char_start e char_end devem ser inteiros.")
            continue

        if start < 0 or end <= start or end > len(case_text):
            errors.append(
                f"Entidade {eid}: offsets [{start}:{end}] invalidos para texto de tamanho {len(case_text)}."
            )
            continue

        texto = str(row["texto"])
        expected_slice = case_text[start:end]

        if texto != expected_slice:
            errors.append(
                f"Entidade {eid}: texto informado '{texto}' difere do trecho real '{expected_slice}' nos offsets [{start}:{end}]."
            )

        etype = str(row.get("type", "")).strip()
        if etype and etype not in VALID_TYPES:
            warnings.append(f"Entidade {eid}: tipo '{etype}' nao faz parte da taxonomia padrao.")

    # Checagem de relacoes linha por linha
    for row_idx, row in df_relations.iterrows():
        src = str(row["source"]).strip()
        tgt = str(row["target"]).strip()
        rel = str(row["relation"]).strip()

        if src not in ent_ids_found:
            errors.append(f"Relacao linha {row_idx}: source '{src}' nao existe em entidades.")
        if tgt not in ent_ids_found:
            errors.append(f"Relacao linha {row_idx}: target '{tgt}' nao existe em entidades.")

        if rel not in VALID_RELATIONS:
            warnings.append(f"Relacao linha {row_idx}: relacao '{rel}' fora do vocabulario padrao.")

        if "polarity" in row:
            pol = str(row["polarity"]).strip()
            if pol and pol not in VALID_POLARITIES:
                warnings.append(f"Relacao linha {row_idx}: polaridade '{pol}' desconhecida.")

        if "certainty" in row:
            cert = str(row["certainty"]).strip()
            if cert and cert not in VALID_CERTAINTIES:
                warnings.append(f"Relacao linha {row_idx}: certeza '{cert}' desconhecida.")

    status = "error" if errors else "ok"
    return {
        "status": status,
        "case_id": case_id,
        "entities_count": len(df_entities),
        "relations_count": len(df_relations),
        "errors": errors,
        "warnings": warnings,
    }


def generate_starter_packs(
    case_texts_path: Path = DEFAULT_CASE_TEXTS,
    splits_path: Path = DEFAULT_SPLITS_PATH,
    silver_dir: Path = DEFAULT_SILVER_DIR,
    gold_dir: Path = DEFAULT_GOLD_DIR,
) -> List[str]:
    """Gera arquivos pre-preenchidos (starter packs) para cada caso do conjunto de teste."""
    splits = json.loads(Path(splits_path).read_text(encoding="utf-8"))
    test_cases = splits.get("test", [])

    df_texts = pd.read_csv(case_texts_path)
    text_by_case = dict(zip(df_texts["case_id"], df_texts["case_text"]))

    df_silver_ent = pd.read_csv(silver_dir / "entidades_tipadas.csv")
    df_silver_rel = pd.read_csv(silver_dir / "relacoes.csv")

    cases_dir = gold_dir / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)

    generated: List[str] = []

    for cid in test_cases:
        case_folder = cases_dir / cid
        case_folder.mkdir(exist_ok=True)

        # Salva o texto bruto com guia de leitura
        c_text = text_by_case.get(cid, "")
        (case_folder / "case_text.txt").write_text(c_text, encoding="utf-8")

        # Filtra entidades do silver para este caso
        ent_subset = df_silver_ent[df_silver_ent["case_id"] == cid].copy()
        ent_file = case_folder / f"{cid}-entities.csv"
        # Se o arquivo ainda nao existir ou estiver vazio, cria starter
        if not ent_file.exists():
            ent_subset[
                ["case_id", "ent_id", "char_start", "char_end", "texto", "type", "concept_code"]
            ].to_csv(ent_file, index=False)

        # Filtra relacoes do silver para este caso
        rel_subset = df_silver_rel[df_silver_rel["case_id"] == cid].copy()
        rel_file = case_folder / f"{cid}-relations.csv"
        if not rel_file.exists():
            rel_subset[
                ["case_id", "source", "target", "relation", "polarity", "certainty"]
            ].to_csv(rel_file, index=False)

        generated.append(cid)

    return generated


def consolidate_gold(
    case_texts_path: Path = DEFAULT_CASE_TEXTS,
    gold_dir: Path = DEFAULT_GOLD_DIR,
) -> Dict[str, Any]:
    """Valida todos os casos anotados e consolida em gold_entidades.csv e gold_relacoes.csv."""
    cases_dir = gold_dir / "cases"
    if not cases_dir.exists():
        raise FileNotFoundError(f"Pasta de casos nao encontrada: {cases_dir}")

    df_texts = pd.read_csv(case_texts_path)
    text_by_case = dict(zip(df_texts["case_id"], df_texts["case_text"]))

    all_entities: List[pd.DataFrame] = []
    all_relations: List[pd.DataFrame] = []
    case_reports: Dict[str, Any] = {}
    has_blocking_errors = False

    for case_folder in sorted(cases_dir.iterdir()):
        if not case_folder.is_dir():
            continue
        cid = case_folder.name
        ent_file = case_folder / f"{cid}-entities.csv"
        rel_file = case_folder / f"{cid}-relations.csv"

        if not ent_file.exists() or not rel_file.exists():
            continue

        df_ent = pd.read_csv(ent_file)
        df_rel = pd.read_csv(rel_file)
        c_text = text_by_case.get(cid, "")

        rep = validate_case_annotation(cid, df_ent, df_rel, c_text)
        case_reports[cid] = rep

        if rep["status"] == "error":
            has_blocking_errors = True
        else:
            all_entities.append(df_ent)
            all_relations.append(df_rel)

    if has_blocking_errors:
        err_msg = "Erros de validacao encontrados no gabarito ouro:\n"
        for cid, rep in case_reports.items():
            if rep["status"] == "error":
                err_msg += f"  [{cid}]: {rep['errors']}\n"
        raise GoldValidationError(err_msg)

    # Concatena e salva
    if all_entities:
        df_final_ent = pd.concat(all_entities, ignore_index=True)
        df_final_ent.to_csv(gold_dir / "gold_entidades.csv", index=False)
    else:
        df_final_ent = pd.DataFrame()

    if all_relations:
        df_final_rel = pd.concat(all_relations, ignore_index=True)
        df_final_rel.to_csv(gold_dir / "gold_relacoes.csv", index=False)
    else:
        df_final_rel = pd.DataFrame()

    manifest = {
        "total_cases_consolidated": len(all_entities),
        "total_gold_entities": len(df_final_ent),
        "total_gold_relations": len(df_final_rel),
        "cases": case_reports,
    }
    with open(gold_dir / "manifest.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return manifest


def main():
    parser = argparse.ArgumentParser(description="Gerenciador e consolidador do Gabarito Ouro.")
    parser.add_argument("--starter-packs", action="store_true", help="Gera starter packs para os casos de teste")
    parser.add_argument("--consolidate", action="store_true", help="Valida e consolida as anotacoes manuais")
    parser.add_argument("--gold-dir", default=str(DEFAULT_GOLD_DIR), help="Diretorio do gold")
    parser.add_argument("--texts", default=str(DEFAULT_CASE_TEXTS), help="Caminho para case_texts.csv")
    args = parser.parse_args()

    gdir = Path(args.gold_dir)
    tpath = Path(args.texts)

    if args.starter_packs:
        cases = generate_starter_packs(case_texts_path=tpath, gold_dir=gdir)
        print(f"Starter packs gerados para {len(cases)} casos em {gdir / 'cases'}")

    if args.consolidate:
        manifest = consolidate_gold(case_texts_path=tpath, gold_dir=gdir)
        print(f"Consolidacao concluida com sucesso!")
        print(f"  Casos validados: {manifest['total_cases_consolidated']}")
        print(f"  Total de entidades ouro: {manifest['total_gold_entities']}")
        print(f"  Total de relacoes ouro: {manifest['total_gold_relations']}")


if __name__ == "__main__":
    main()
