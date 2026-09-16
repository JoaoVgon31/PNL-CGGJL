"""CSVs de nós/arestas (combinado + estratégias) -> JSON consumido pelo site.

Roda como script direto: `python3 tools/export_graph_data.py`, sempre a
partir do checkout do repositório (é o que o workflow de deploy faz). Fica
resiliente a fontes parciais de propósito: hoje só `dicionarios/output/` e
`stopwords/output/` têm os 56 casos, `tokenizacao/output/` e
`normalizacao/output/` só têm o caso de exemplo, e `sintagmas/` ainda não
publica nós/arestas — o manifesto reflete exatamente essa cobertura e cresce
sozinho conforme cada estratégia publicar mais casos.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from graph_csv import read_case_texts, read_edges_csv, read_nodes_csv

# Ordem também usada pelo front-end para desenhar as abas da esquerda pra
# direita; a chave é o nome da aba, o valor é o caminho (relativo à raiz de
# project1/) de onde vêm os CSVs daquela estratégia.
STRATEGY_SOURCES = {
    "combinado": Path("data/processed"),
    "tokenizacao": Path("src/tokenizacao/output"),
    "stopwords": Path("src/stopwords/output"),
    "dicionarios": Path("src/dicionarios/output"),
    "sintagmas": Path("src/sintagmas/output"),
    "normalizacao": Path("src/normalizacao/output"),
}

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "visualizer" / "data"


def discover_cases(project_root: Path) -> dict[str, dict[str, Path]]:
    """Varre STRATEGY_SOURCES; devolve {case_id: {estrategia: diretorio}}.

    Só inclui (estratégia, case_id) quando nodes.csv E edges.csv existem —
    um par incompleto é tratado como fonte ausente, não como erro.
    """
    cases: dict[str, dict[str, Path]] = {}
    for strategy, relative_dir in STRATEGY_SOURCES.items():
        directory = project_root / relative_dir
        if not directory.is_dir():
            continue
        for nodes_path in sorted(directory.glob("*-nodes.csv")):
            case_id = nodes_path.name[: -len("-nodes.csv")]
            edges_path = directory / f"{case_id}-edges.csv"
            if not edges_path.exists():
                continue
            cases.setdefault(case_id, {})[strategy] = directory
    return cases


def build_case_payload(
    case_id: str, sources: dict[str, Path], case_texts: dict[str, str]
) -> dict:
    """Monta o payload de um caso: grafos disponíveis + case_text se houver."""
    graphs = {}
    for strategy, directory in sources.items():
        graphs[strategy] = {
            "nodes": read_nodes_csv(directory / f"{case_id}-nodes.csv"),
            "edges": read_edges_csv(directory / f"{case_id}-edges.csv"),
        }
    payload: dict = {"case_id": case_id, "graphs": graphs}
    if case_id in case_texts:
        payload["case_text"] = case_texts[case_id]
    return payload


def build_manifest(payloads: dict[str, dict]) -> dict:
    """Lista ordenada de casos + quais grafos cada um tem, para o dropdown/abas."""
    return {
        "cases": [
            {"case_id": case_id, "graphs": sorted(payloads[case_id]["graphs"].keys())}
            for case_id in sorted(payloads)
        ]
    }


def export_all(project_root: Path, output_dir: Path) -> dict:
    """Gera <case_id>.json + manifest.json em output_dir. Devolve o manifesto."""
    case_texts = read_case_texts(project_root / "data" / "case_texts.csv")
    discovered = discover_cases(project_root)

    output_dir.mkdir(parents=True, exist_ok=True)

    payloads = {
        case_id: build_case_payload(case_id, sources, case_texts)
        for case_id, sources in discovered.items()
    }

    for case_id, payload in payloads.items():
        case_path = output_dir / f"{case_id}.json"
        case_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    manifest = build_manifest(payloads)
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    return manifest


if __name__ == "__main__":
    result_manifest = export_all(PROJECT_ROOT, DEFAULT_OUTPUT_DIR)
    print(f"{len(result_manifest['cases'])} caso(s) exportado(s) para {DEFAULT_OUTPUT_DIR}")
