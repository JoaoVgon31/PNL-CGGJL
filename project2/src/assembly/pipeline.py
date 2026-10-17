# -*- coding: utf-8 -*-
"""Pipeline de Montagem de Grafos em Lote para o Projeto 2.

Executa a montagem e deduplicacao para todos os casos da amostra (ou subconjunto),
gerando os arquivos <case_id>-nodes.csv e <case_id>-edges.csv na pasta de saida,
alem do relatorio de resumo geral (_resumo.csv).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Garante suporte UTF-8 no terminal Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import pandas as pd

from project2.src.assembly.graph_builder import CaseGraphBuilder

DEFAULT_ENTITIES_PATH = Path("project2/data/silver/entidades_tipadas.csv")
DEFAULT_RELATIONS_PATH = Path("project2/data/silver/relacoes.csv")
DEFAULT_OUTPUT_DIR = Path("project2/data/processed")


class BatchGraphPipeline:
    """Executa a montagem dos grafos clinicos em lote."""

    def __init__(
        self,
        entities_path: Path = DEFAULT_ENTITIES_PATH,
        relations_path: Path = DEFAULT_RELATIONS_PATH,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
    ):
        self.entities_path = Path(entities_path)
        self.relations_path = Path(relations_path)
        self.output_dir = Path(output_dir)
        self.builder = CaseGraphBuilder()

    def run(self, case_ids: Optional[List[str]] = None) -> pd.DataFrame:
        """Executa a esteira em lote e retorna o DataFrame de resumo."""
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if not self.entities_path.exists():
            raise FileNotFoundError(f"Arquivo de entidades nao encontrado: {self.entities_path}")
        if not self.relations_path.exists():
            raise FileNotFoundError(f"Arquivo de relacoes nao encontrado: {self.relations_path}")

        df_entities = pd.read_csv(self.entities_path)
        df_relations = pd.read_csv(self.relations_path)

        available_cases = sorted(df_entities["case_id"].dropna().unique().tolist())
        if case_ids:
            target_cases = [c for c in case_ids if c in available_cases]
        else:
            target_cases = available_cases

        print(f"Iniciando montagem de grafos para {len(target_cases)} casos...")
        summary_rows: List[Dict[str, Any]] = []

        for cid in target_cases:
            t0 = time.time()
            try:
                df_nodes, df_edges = self.builder.build_case_graph(
                    case_id=cid,
                    df_entities=df_entities,
                    df_relations=df_relations,
                )

                # Exporta CSVs individuais
                nodes_out = self.output_dir / f"{cid}-nodes.csv"
                edges_out = self.output_dir / f"{cid}-edges.csv"

                df_nodes.to_csv(nodes_out, index=False)
                df_edges.to_csv(edges_out, index=False)

                t1 = time.time()

                n_concepts = (df_nodes["type"] == "Concept").sum()
                n_clinical = len(df_nodes) - n_concepts
                e_same_as = (df_edges["relation"] == "SAME_AS").sum()
                e_clinical = len(df_edges) - e_same_as

                summary_rows.append(
                    {
                        "case_id": cid,
                        "status": "ok",
                        "total_nos": len(df_nodes),
                        "nos_clinicos": n_clinical,
                        "nos_conceito": n_concepts,
                        "total_arestas": len(df_edges),
                        "arestas_clinicas": e_clinical,
                        "arestas_same_as": e_same_as,
                        "tempo_s": round(t1 - t0, 3),
                        "erro": "",
                    }
                )
            except Exception as ex:
                t1 = time.time()
                summary_rows.append(
                    {
                        "case_id": cid,
                        "status": "erro",
                        "total_nos": 0,
                        "nos_clinicos": 0,
                        "nos_conceito": 0,
                        "total_arestas": 0,
                        "arestas_clinicas": 0,
                        "arestas_same_as": 0,
                        "tempo_s": round(t1 - t0, 3),
                        "erro": str(ex),
                    }
                )

        df_summary = pd.DataFrame(summary_rows)
        summary_file = self.output_dir / "_resumo.csv"
        df_summary.to_csv(summary_file, index=False)

        print("\n" + "=" * 70)
        print("RELATORIO DE MONTAGEM DE GRAFOS EM LOTE (Estacao 5 - George)")
        print("=" * 70)
        print(f"Total de casos processados: {len(target_cases)}")
        print(f"Casos com sucesso:          {(df_summary['status'] == 'ok').sum()}")
        print(f"Casos com erro:             {(df_summary['status'] == 'erro').sum()}")
        print(f"Total de nós gerados:       {df_summary['total_nos'].sum()}")
        print(f"Total de arestas geradas:   {df_summary['total_arestas'].sum()}")
        print(f"Resumo consolidado salvo em: {summary_file}")
        print("=" * 70 + "\n")

        return df_summary


def main():
    parser = argparse.ArgumentParser(description="Pipeline de montagem do grafo final em lote.")
    parser.add_argument("--entities", default=str(DEFAULT_ENTITIES_PATH), help="Caminho para entidades_tipadas.csv")
    parser.add_argument("--relations", default=str(DEFAULT_RELATIONS_PATH), help="Caminho para relacoes.csv")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_DIR), help="Pasta de saida dos CSVs")
    parser.add_argument("--case-ids", help="Lista de case_ids separados por virgula")
    args = parser.parse_args()

    cids = [c.strip() for c in args.case_ids.split(",")] if args.case_ids else None
    pipeline = BatchGraphPipeline(
        entities_path=Path(args.entities),
        relations_path=Path(args.relations),
        output_dir=Path(args.output),
    )
    pipeline.run(case_ids=cids)


if __name__ == "__main__":
    main()
