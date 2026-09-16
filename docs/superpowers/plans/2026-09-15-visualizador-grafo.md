# Visualizador Interativo do Grafo de Conhecimento — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar ao professor um site estático (GitHub Pages) onde ele navega, para qualquer caso da amostra, o grafo combinado e o grafo de cada estratégia isolada, com cada aresta auditável contra o `case_text` original.

**Architecture:** Um script Python (`project1/tools/export_graph_data.py`) varre os CSVs de nós/arestas já produzidos (`project1/data/processed/` + `project1/src/*/output/`) e gera um JSON por caso + um manifesto em `project1/visualizer/data/`. Um site HTML/JS puro (Cytoscape.js vendorizado) lê esses JSONs e desenha o grafo, com abas por estratégia e uma gaveta de detalhes que destaca a evidência no texto completo do caso. Um workflow do GitHub Actions roda o script e publica `project1/visualizer/` via `actions/deploy-pages` a cada push relevante.

**Tech Stack:** Python 3 (stdlib apenas) para a exportação; HTML/CSS/JS puro + Cytoscape.js 3.30.2 (vendorizado) para o site; GitHub Actions (`actions/checkout`, `actions/setup-python`, `actions/upload-pages-artifact`, `actions/deploy-pages`) para o deploy.

## Global Constraints

- Sem framework JS com bundler (React/Vite) — HTML/JS puro, Cytoscape.js vendorizado localmente, sem CDN. (spec: "Site")
- `project1/tools/` usa só a biblioteca padrão do Python — mesma restrição das estratégias de extração. (spec: "`export_graph_data.py`")
- Testes Python em `unittest`, convenção do repo: `python3 -m unittest discover -s <dir-de-testes> -p "test_*.py"`.
- `sample/` nunca é versionado. O único recorte permitido é `project1/data/case_texts.csv` (`case_id`, `case_text`). (spec: "Bloqueio de dados encontrado e decisão")
- Nada de artefato gerado (`project1/visualizer/data/*.json`) é commitado em qualquer branch — só o workflow gera isso, em CI, na hora do deploy. (spec: "Deploy (GitHub Pages)")
- Cor de nó nunca é o único sinal de tipo — todo nó também mostra o tipo como texto (rótulo) e `Concept` usa uma forma (losango) diferente das entidades clínicas (elipse/retângulo). (spec: "Codificação visual")
- Sem diff automático entre abas de estratégia — cada aba redesenha do zero. (spec: "Fora de escopo")

---

## Contexto que os próximos agentes precisam saber (não é óbvio pelo código)

- **`sample/cases.csv` existe localmente neste checkout** (`/Users/joaovitorgoncalvesoliveira/Documents/Desenvolvimento/UNICAMP/MC859/PNL-CGGJL/sample/cases.csv`, 56 linhas, colunas `article_id,age,case_id,case_text,gender`) mas está no `.gitignore` — é assim que a Task 3 consegue gerar `project1/data/case_texts.csv` de verdade, sem esperar por ninguém.
- **Cobertura real dos parsers hoje** (verificado por contagem de arquivo, não suposição): `dicionarios/output/` e `stopwords/output/` têm os 56 casos; `tokenizacao/output/` e `normalizacao/output/` só têm `PMC5137649_01`; `src/sintagmas/` não tem pasta `output/` nem CSVs de nós/arestas (só CoNLL/IOB2, conforme `src/sintagmas/README.md`); `data/processed/` (grafo combinado) só tem `PMC5137649_01`. **Isso é esperado, não é bug** — o código deve tratar cada fonte como opcional.
- **Formato de `attributes`** (mesmo em todas as estratégias, ex. `src/stopwords/core/models.py:40`): `"chave=valor; chave=valor"`, só com atributos preenchidos, sem escapar `; ` dentro de um valor. Não existe hoje nenhum parser reverso no repo — foi escrito do zero na Task 1 e a técnica (regex que só quebra em `; ` quando o que segue parece `identificador=`) já foi validada manualmente contra as 38 arestas com offset de `PMC5137649_01`: 0 mismatches em `case_text[char_start:char_end] == evidence_text`.
- **Tipos de nó reais** (`type` em qualquer `*-nodes.csv` do repo hoje): `AnatomicalSite, Concept, Diagnosis, Exam, ExamResult, Finding, History, Medication, Outcome, Patient, Symptom, Treatment` — exatamente 12, batendo com o modelo lógico do README.
- **Paleta de cor**: a paleta categórica padrão do skill `dataviz` só garante 8 cores seguras (e só as 3 primeiras contra qualquer par simultâneo, que é o caso realista de um grafo forçado onde qualquer par de tipos pode ficar vizinho). Em vez de inventar 4 cores novas não validadas, a Task 5 reaproveita as 8 cores validadas + 3 formas (elipse/retângulo/losango) — 8 tipos com cor única (elipse), 3 tipos reaproveitando cor de um tipo relacionado mas com forma de retângulo, e `Concept` em cinza+losango (fora da paleta categórica, porque não é uma entidade clínica). Isso está documentado na Task 5, não precisa ser re-derivado.
- **Import cross-estratégia é uma armadilha conhecida**: `pipelines/notebooks/grafo_combinado.ipynb` comenta que os pacotes de `src/{tokenizacao,sintagmas,dicionarios}` são "pastas planas" com nomes de módulo colidentes, exigindo malabarismo de `sys.path`. `project1/tools/` evita isso de propósito: nunca importa nada de `src/*` — só lê os CSVs pelo formato documentado (contrato comum). `project1/tools/graph_csv.py` e `export_graph_data.py` também não usam pacote (`__init__.py`); cada um insere o próprio diretório em `sys.path` e importa por nome simples, mesmo padrão de isolamento que o notebook já precisou usar entre as estratégias.

---

### Task 1: `graph_csv.py` — parsing de CSV/attributes

**Files:**
- Create: `project1/tools/graph_csv.py`
- Test: `project1/tools/tests/test_graph_csv.py`

**Interfaces:**
- Produces: `parse_attributes(raw: str) -> dict[str, str]`, `read_case_texts(path: Path) -> dict[str, str]`, `read_nodes_csv(path: Path) -> list[dict]` (cada item: `{"node_id": str, "type": str, "label": str, "attributes": dict[str,str]}`), `read_edges_csv(path: Path) -> list[dict]` (cada item: `{"edge_id": str, "source_id": str, "target_id": str, "relation": str, "attributes": dict[str,str]}`) — usadas por `export_graph_data.py` (Task 2).

- [ ] **Step 1: Criar a pasta de testes e escrever os testes de `parse_attributes`**

Crie `project1/tools/tests/__init__.py` vazio (só para o discovery achar a pasta) e `project1/tools/tests/test_graph_csv.py`:

```python
import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from graph_csv import parse_attributes, read_case_texts, read_edges_csv, read_nodes_csv


class ParseAttributesTests(unittest.TestCase):
    def test_empty_string_returns_empty_dict(self):
        self.assertEqual(parse_attributes(""), {})

    def test_single_pair(self):
        self.assertEqual(parse_attributes("polarity=present"), {"polarity": "present"})

    def test_multiple_pairs(self):
        raw = "polarity=present; duration=3 days"
        self.assertEqual(parse_attributes(raw), {"polarity": "present", "duration": "3 days"})

    def test_value_containing_semicolon_is_not_split_early(self):
        raw = "evidence_text=Her pain resolved; she was discharged home; trigger=resolved; certainty=asserted"
        self.assertEqual(
            parse_attributes(raw),
            {
                "evidence_text": "Her pain resolved; she was discharged home",
                "trigger": "resolved",
                "certainty": "asserted",
            },
        )


class ReadCaseTextsTests(unittest.TestCase):
    def test_missing_file_returns_empty_dict(self):
        self.assertEqual(read_case_texts(Path("/nonexistent/case_texts.csv")), {})

    def test_reads_case_id_and_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "case_texts.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=("case_id", "case_text"))
                writer.writeheader()
                writer.writerow({"case_id": "CASE1", "case_text": "Texto, com vírgula."})
            self.assertEqual(read_case_texts(path), {"CASE1": "Texto, com vírgula."})


class ReadNodesEdgesCsvTests(unittest.TestCase):
    def test_read_nodes_csv_parses_attributes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "CASE1-nodes.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=("case_id", "node_id", "type", "label", "attributes")
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "case_id": "CASE1",
                        "node_id": "S1",
                        "type": "Symptom",
                        "label": "nausea",
                        "attributes": "polarity=present",
                    }
                )
            nodes = read_nodes_csv(path)
            self.assertEqual(
                nodes,
                [
                    {
                        "node_id": "S1",
                        "type": "Symptom",
                        "label": "nausea",
                        "attributes": {"polarity": "present"},
                    }
                ],
            )

    def test_read_edges_csv_parses_attributes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "CASE1-edges.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=("case_id", "edge_id", "source_id", "target_id", "relation", "attributes"),
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "case_id": "CASE1",
                        "edge_id": "e1",
                        "source_id": "P1",
                        "target_id": "S1",
                        "relation": "HAS_SYMPTOM",
                        "attributes": "evidence_text=she had nausea; char_start=10; char_end=20",
                    }
                )
            edges = read_edges_csv(path)
            self.assertEqual(
                edges,
                [
                    {
                        "edge_id": "e1",
                        "source_id": "P1",
                        "target_id": "S1",
                        "relation": "HAS_SYMPTOM",
                        "attributes": {
                            "evidence_text": "she had nausea",
                            "char_start": "10",
                            "char_end": "20",
                        },
                    }
                ],
            )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar os testes e confirmar que falham por import**

Run: `python3 -m unittest discover -s project1/tools/tests -p "test_*.py" -v`
Expected: `ModuleNotFoundError: No module named 'graph_csv'` (o arquivo ainda não existe).

- [ ] **Step 3: Implementar `project1/tools/graph_csv.py`**

```python
"""Leitura genérica de CSVs no contrato comum (nós/arestas) e do recorte de case_text.

Não importa nada de src/*/core — os pacotes de estratégia têm nomes de módulo
que colidem entre si (ver pipelines/notebooks/grafo_combinado.ipynb), então
este módulo só entende o formato de arquivo (colunas + 'attributes'
serializado), igual a qualquer estratégia que siga o contrato comum.
"""

import csv
import re
from pathlib import Path

NODE_COLUMNS = ("case_id", "node_id", "type", "label", "attributes")
EDGE_COLUMNS = ("case_id", "edge_id", "source_id", "target_id", "relation", "attributes")

# 'serialize_attributes' (repetido em cada estratégia, ex. stopwords/core/models.py)
# junta pares 'chave=valor' com '; ' sem escapar valores que contenham esse
# delimitador (ex.: evidence_text com pontuação). Só quebramos em '; ' quando o
# que vem depois parece uma nova chave (identificador seguido de '='), porque
# nenhuma chave conhecida do contrato comum tem esse formato dentro do valor.
_ATTR_SPLIT_RE = re.compile(r"; (?=[A-Za-z_][A-Za-z0-9_]*=)")


def parse_attributes(raw: str) -> dict[str, str]:
    """Reverte 'chave=valor; chave=valor' para dict. String vazia -> {}."""
    if not raw:
        return {}
    attributes: dict[str, str] = {}
    for part in _ATTR_SPLIT_RE.split(raw):
        key, separator, value = part.partition("=")
        if not separator:
            continue
        attributes[key] = value
    return attributes


def read_case_texts(path: Path) -> dict[str, str]:
    """Lê case_texts.csv (case_id, case_text) -> {case_id: case_text}.

    Arquivo ausente (ex.: alguém rodando local sem tê-lo gerado ainda) não é
    erro fatal: devolve {} e quem chama trata como 'sem case_text'.
    """
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["case_id"]: row["case_text"] for row in csv.DictReader(handle)}


def read_nodes_csv(path: Path) -> list[dict]:
    """Lê <case_id>-nodes.csv -> lista de dicts com attributes já em dict."""
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        {
            "node_id": row["node_id"],
            "type": row["type"],
            "label": row["label"],
            "attributes": parse_attributes(row["attributes"]),
        }
        for row in rows
    ]


def read_edges_csv(path: Path) -> list[dict]:
    """Lê <case_id>-edges.csv -> lista de dicts com attributes já em dict."""
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return [
        {
            "edge_id": row["edge_id"],
            "source_id": row["source_id"],
            "target_id": row["target_id"],
            "relation": row["relation"],
            "attributes": parse_attributes(row["attributes"]),
        }
        for row in rows
    ]
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `python3 -m unittest discover -s project1/tools/tests -p "test_*.py" -v`
Expected: `OK` (8 testes).

- [ ] **Step 5: Commit**

```bash
git add project1/tools/graph_csv.py project1/tools/tests/__init__.py project1/tools/tests/test_graph_csv.py
git commit -m "feat: adiciona parsing de CSV/attributes do contrato comum para o visualizador"
```

---

### Task 2: `export_graph_data.py` — descoberta de casos, payload por caso e manifesto

**Files:**
- Create: `project1/tools/export_graph_data.py`
- Test: `project1/tools/tests/test_export_graph_data.py`

**Interfaces:**
- Consumes: `read_case_texts`, `read_nodes_csv`, `read_edges_csv` de `graph_csv.py` (Task 1).
- Produces: `discover_cases(project_root: Path) -> dict[str, dict[str, Path]]`, `build_case_payload(case_id: str, sources: dict[str, Path], case_texts: dict[str, str]) -> dict`, `build_manifest(payloads: dict[str, dict]) -> dict`, `export_all(project_root: Path, output_dir: Path) -> dict` — `export_all` é o que o workflow da Task 7 chama (via `if __name__ == "__main__"`), e o formato de `<case_id>.json`/`manifest.json` que ele escreve é o que `app.js` (Task 5) consome.

- [ ] **Step 1: Escrever os testes**

Crie `project1/tools/tests/test_export_graph_data.py`:

```python
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from export_graph_data import build_case_payload, build_manifest, discover_cases, export_all


def _write_csv(path: Path, columns: tuple, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


NODE_COLUMNS = ("case_id", "node_id", "type", "label", "attributes")
EDGE_COLUMNS = ("case_id", "edge_id", "source_id", "target_id", "relation", "attributes")


def _write_case_graph(directory: Path, case_id: str) -> None:
    _write_csv(
        directory / f"{case_id}-nodes.csv",
        NODE_COLUMNS,
        [{"case_id": case_id, "node_id": "P1", "type": "Patient", "label": "case", "attributes": ""}],
    )
    _write_csv(directory / f"{case_id}-edges.csv", EDGE_COLUMNS, [])


class DiscoverCasesTests(unittest.TestCase):
    def test_finds_cases_across_available_sources_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_case_graph(root / "data" / "processed", "CASE1")
            _write_case_graph(root / "src" / "stopwords" / "output", "CASE1")
            _write_case_graph(root / "src" / "stopwords" / "output", "CASE2")
            # src/sintagmas/output nem existe -- não deve quebrar a varredura.

            cases = discover_cases(root)

            self.assertEqual(set(cases.keys()), {"CASE1", "CASE2"})
            self.assertEqual(set(cases["CASE1"].keys()), {"combinado", "stopwords"})
            self.assertEqual(set(cases["CASE2"].keys()), {"stopwords"})

    def test_ignores_nodes_csv_without_matching_edges_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = root / "src" / "tokenizacao" / "output"
            directory.mkdir(parents=True)
            _write_csv(
                directory / "CASE1-nodes.csv",
                NODE_COLUMNS,
                [{"case_id": "CASE1", "node_id": "P1", "type": "Patient", "label": "x", "attributes": ""}],
            )
            # sem CASE1-edges.csv

            cases = discover_cases(root)

            self.assertEqual(cases, {})


class BuildCasePayloadTests(unittest.TestCase):
    def test_includes_case_text_when_known(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _write_case_graph(directory, "CASE1")
            sources = {"combinado": directory}

            payload = build_case_payload("CASE1", sources, {"CASE1": "texto do caso"})

            self.assertEqual(payload["case_text"], "texto do caso")
            self.assertEqual(list(payload["graphs"].keys()), ["combinado"])

    def test_omits_case_text_when_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            _write_case_graph(directory, "CASE1")
            sources = {"combinado": directory}

            payload = build_case_payload("CASE1", sources, {})

            self.assertNotIn("case_text", payload)


class BuildManifestTests(unittest.TestCase):
    def test_lists_cases_sorted_with_their_graph_keys(self):
        payloads = {
            "CASE2": {"graphs": {"stopwords": {}}},
            "CASE1": {"graphs": {"combinado": {}, "stopwords": {}}},
        }

        manifest = build_manifest(payloads)

        self.assertEqual(
            manifest,
            {
                "cases": [
                    {"case_id": "CASE1", "graphs": ["combinado", "stopwords"]},
                    {"case_id": "CASE2", "graphs": ["stopwords"]},
                ]
            },
        )


class ExportAllTests(unittest.TestCase):
    def test_writes_case_files_and_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_case_graph(root / "data" / "processed", "CASE1")
            _write_case_graph(root / "src" / "stopwords" / "output", "CASE1")
            _write_case_graph(root / "src" / "stopwords" / "output", "CASE2")
            _write_csv(
                root / "data" / "case_texts.csv",
                ("case_id", "case_text"),
                [{"case_id": "CASE1", "case_text": "texto do CASE1"}],
            )
            output_dir = root / "visualizer" / "data"

            manifest = export_all(root, output_dir)

            self.assertEqual(
                manifest,
                {
                    "cases": [
                        {"case_id": "CASE1", "graphs": ["combinado", "stopwords"]},
                        {"case_id": "CASE2", "graphs": ["stopwords"]},
                    ]
                },
            )
            self.assertEqual(json.loads((output_dir / "manifest.json").read_text()), manifest)

            case1 = json.loads((output_dir / "CASE1.json").read_text())
            self.assertEqual(case1["case_text"], "texto do CASE1")
            self.assertEqual(set(case1["graphs"].keys()), {"combinado", "stopwords"})

            case2 = json.loads((output_dir / "CASE2.json").read_text())
            self.assertNotIn("case_text", case2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar os testes e confirmar que falham por import**

Run: `python3 -m unittest discover -s project1/tools/tests -p "test_*.py" -v`
Expected: `ModuleNotFoundError: No module named 'export_graph_data'`.

- [ ] **Step 3: Implementar `project1/tools/export_graph_data.py`**

```python
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
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `python3 -m unittest discover -s project1/tools/tests -p "test_*.py" -v`
Expected: `OK` (14 testes: 8 da Task 1 + 6 novos).

- [ ] **Step 5: Rodar contra os dados reais do repo (smoke test, não é o deploy final)**

Run:
```bash
python3 project1/tools/export_graph_data.py
```
Expected: imprime `56 caso(s) exportado(s) para .../project1/visualizer/data` (56 porque `discover_cases` já acha todo `case_id` com nodes+edges em qualquer estratégia, mesmo sem `case_text` ainda — a Task 3 é que vai gerar `case_texts.csv`). Confira com:
```bash
python3 -c "import json; m = json.load(open('project1/visualizer/data/manifest.json')); print([c for c in m['cases'] if c['case_id'] == 'PMC5137649_01'])"
```
Expected: `[{'case_id': 'PMC5137649_01', 'graphs': ['combinado', 'dicionarios', 'normalizacao', 'stopwords', 'tokenizacao']}]`.

Depois do smoke test, apague a saída gerada (ela não é commitada, ver Global Constraints):
```bash
rm -rf project1/visualizer/data
```

- [ ] **Step 6: Commit**

```bash
git add project1/tools/export_graph_data.py project1/tools/tests/test_export_graph_data.py
git commit -m "feat: adiciona descoberta de casos e exportação de grafo/manifesto"
```

---

### Task 3: `generate_case_texts.py` e o `case_texts.csv` real

**Files:**
- Create: `project1/tools/generate_case_texts.py`
- Test: `project1/tools/tests/test_generate_case_texts.py`
- Create (dado, não código): `project1/data/case_texts.csv`

**Interfaces:**
- Produces: `generate(cases_csv: Path, output_csv: Path) -> int` — usado só localmente por quem tem a amostra; não é chamado pelo workflow (CI não tem `sample/`).

- [ ] **Step 1: Escrever o teste**

Crie `project1/tools/tests/test_generate_case_texts.py`:

```python
import csv
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generate_case_texts import generate


class GenerateTests(unittest.TestCase):
    def test_copies_case_id_and_case_text_columns_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            cases_csv = Path(tmp) / "cases.csv"
            with cases_csv.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle, fieldnames=("article_id", "age", "case_id", "case_text", "gender")
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "article_id": "PMC1",
                        "age": "44.0",
                        "case_id": "PMC1_01",
                        "case_text": "A patient, with a comma, presented.",
                        "gender": "Female",
                    }
                )
            output_csv = Path(tmp) / "case_texts.csv"

            count = generate(cases_csv, output_csv)

            self.assertEqual(count, 1)
            with output_csv.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(
                rows, [{"case_id": "PMC1_01", "case_text": "A patient, with a comma, presented."}]
            )
            self.assertEqual(list(rows[0].keys()), ["case_id", "case_text"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Rodar e confirmar que falha por import**

Run: `python3 -m unittest discover -s project1/tools/tests -p "test_*.py" -v`
Expected: `ModuleNotFoundError: No module named 'generate_case_texts'`.

- [ ] **Step 3: Implementar `project1/tools/generate_case_texts.py`**

```python
"""Gera project1/data/case_texts.csv a partir de sample/cases.csv (local).

sample/ não é versionado (ver .gitignore e project1/README.md), então este
script só funciona em quem já tem a amostra do MultiCaRe baixada localmente.
O resultado (case_id, case_text) é commitado especificamente para o
visualizador poder mostrar o texto completo do caso mesmo num runner de CI
sem acesso a sample/. Rodar de novo e recommitar sempre que a amostra local
mudar (novos casos, texto corrigido).
"""

import csv
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CASE_TEXTS_COLUMNS = ("case_id", "case_text")


def generate(cases_csv: Path, output_csv: Path) -> int:
    with cases_csv.open(encoding="utf-8", newline="") as handle:
        rows = [
            {"case_id": row["case_id"], "case_text": row["case_text"]}
            for row in csv.DictReader(handle)
        ]
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CASE_TEXTS_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


if __name__ == "__main__":
    cases_csv_path = PROJECT_ROOT.parent / "sample" / "cases.csv"
    output_csv_path = PROJECT_ROOT / "data" / "case_texts.csv"
    if not cases_csv_path.exists():
        print(
            f"não encontrado: {cases_csv_path} (amostra local necessária, não versionada)",
            file=sys.stderr,
        )
        raise SystemExit(1)
    written = generate(cases_csv_path, output_csv_path)
    print(f"{output_csv_path.relative_to(PROJECT_ROOT.parent)}: {written} casos")
```

- [ ] **Step 4: Rodar os testes e confirmar que passam**

Run: `python3 -m unittest discover -s project1/tools/tests -p "test_*.py" -v`
Expected: `OK` (15 testes).

- [ ] **Step 5: Gerar `project1/data/case_texts.csv` de verdade**

Este repositório já tem `sample/cases.csv` localmente (56 linhas). Rode:
```bash
python3 project1/tools/generate_case_texts.py
```
Expected: imprime `sample/data/case_texts.csv: 56 casos` (o caminho impresso é relativo à raiz do repo). Confira:
```bash
python3 -c "
import csv
with open('project1/data/case_texts.csv', encoding='utf-8', newline='') as f:
    rows = list(csv.DictReader(f))
print(len(rows), list(rows[0].keys()))
"
```
Expected: `56 ['case_id', 'case_text']`.

- [ ] **Step 6: Confirmar a invariante de auditoria numa amostra real**

Esta é a garantia central da gaveta de detalhes (Task 6): `case_text[char_start:char_end] == evidence_text`. Rode contra o caso combinado real:
```bash
python3 -c "
import sys, csv
sys.path.insert(0, 'project1/tools')
from graph_csv import read_case_texts, read_edges_csv
texts = read_case_texts(__import__('pathlib').Path('project1/data/case_texts.csv'))
edges = read_edges_csv(__import__('pathlib').Path('project1/data/processed/PMC5137649_01-edges.csv'))
text = texts['PMC5137649_01']
checked = mismatches = 0
for e in edges:
    a = e['attributes']
    if {'char_start', 'char_end', 'evidence_text'} <= a.keys():
        checked += 1
        start, end = int(a['char_start']), int(a['char_end'])
        if text[start:end] != a['evidence_text']:
            mismatches += 1
print(checked, 'arestas checadas,', mismatches, 'mismatch(es)')
"
```
Expected: `38 arestas checadas, 0 mismatch(es)`.

- [ ] **Step 7: Commit**

```bash
git add project1/tools/generate_case_texts.py project1/tools/tests/test_generate_case_texts.py project1/data/case_texts.csv
git commit -m "feat: gera case_texts.csv versionado para o visualizador auditar evidência"
```

---

### Task 4: Vendorizar Cytoscape.js e montar o shell estático (layout B)

**Files:**
- Create: `project1/visualizer/vendor/cytoscape.min.js`
- Create: `project1/visualizer/index.html`
- Create: `project1/visualizer/style.css`

**Interfaces:**
- Produces: elementos DOM com os ids `case-select`, `case-options` (datalist), `tabs`, `cy`, `legend`, `empty-state`, `drawer`, `drawer-close`, `drawer-body` — `app.js` (Task 5/6) depende exatamente desses ids.

- [ ] **Step 1: Baixar e verificar o Cytoscape.js vendorizado**

```bash
mkdir -p project1/visualizer/vendor
curl -sL --max-time 30 -o project1/visualizer/vendor/cytoscape.min.js \
  https://unpkg.com/cytoscape@3.30.2/dist/cytoscape.min.js
shasum -a 256 project1/visualizer/vendor/cytoscape.min.js
```
Expected: o sha256 impresso é `83e8c54a6bec655bfd81df07df605649c268af69aeca67a5ea2da54ea42dac81` (validado ao escrever este plano). Se vier diferente, o CDN mudou o conteúdo do pacote 3.30.2 — pare e confirme a versão antes de continuar. Confirme também que é JS válido:
```bash
node --check project1/visualizer/vendor/cytoscape.min.js && echo "SYNTAX OK"
```
Expected: `SYNTAX OK`.

- [ ] **Step 2: Criar `project1/visualizer/index.html`**

```html
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Visualizador de Grafos — PNL-CGGJL</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header class="topbar">
    <h1>Grafo de Conhecimento — Casos Clínicos</h1>
    <div class="case-picker">
      <label for="case-select">Caso</label>
      <input id="case-select" list="case-options" placeholder="Buscar case_id…" autocomplete="off">
      <datalist id="case-options"></datalist>
    </div>
  </header>

  <nav class="tabs" id="tabs" role="tablist" aria-label="Estratégia"></nav>

  <main class="canvas-wrap">
    <div id="cy"></div>
    <aside class="legend" id="legend" aria-label="Legenda e filtro de tipos"></aside>
    <p class="empty-state" id="empty-state" hidden></p>
  </main>

  <section class="drawer" id="drawer" hidden>
    <button class="drawer-close" id="drawer-close" aria-label="Fechar detalhes">×</button>
    <div class="drawer-body" id="drawer-body"></div>
  </section>

  <script src="vendor/cytoscape.min.js"></script>
  <script src="app.js"></script>
</body>
</html>
```

- [ ] **Step 3: Criar `project1/visualizer/style.css`**

```css
:root {
  color-scheme: light dark;
  --bg: #fcfcfb;
  --text: #0b0b0b;
  --text-secondary: #52514e;
  --border: #d8d7d2;
  --surface: #ffffff;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #1a1a19;
    --text: #ffffff;
    --text-secondary: #c3c2b7;
    --border: #3a3a38;
    --surface: #232322;
  }
}

* { box-sizing: border-box; }

html, body {
  margin: 0;
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: var(--bg);
  color: var(--text);
}

body {
  display: flex;
  flex-direction: column;
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  gap: 16px;
  flex-wrap: wrap;
}

.topbar h1 {
  font-size: 16px;
  margin: 0;
}

.case-picker {
  display: flex;
  align-items: center;
  gap: 8px;
}

.case-picker input {
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: 4px;
  background: var(--surface);
  color: var(--text);
  min-width: 220px;
}

.tabs {
  display: flex;
  gap: 4px;
  padding: 8px 16px;
  border-bottom: 1px solid var(--border);
  overflow-x: auto;
}

.tab {
  padding: 6px 12px;
  border: 1px solid var(--border);
  border-radius: 999px;
  background: var(--surface);
  color: var(--text);
  cursor: pointer;
  font-size: 13px;
  white-space: nowrap;
}

.tab[aria-selected="true"] {
  background: var(--text);
  color: var(--bg);
  border-color: var(--text);
}

.tab:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.canvas-wrap {
  position: relative;
  flex: 1;
  min-height: 0;
}

#cy {
  position: absolute;
  inset: 0;
}

.legend {
  position: absolute;
  top: 12px;
  right: 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  max-height: 60vh;
  overflow-y: auto;
  font-size: 12px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  border: none;
  background: none;
  color: var(--text);
  cursor: pointer;
  padding: 2px 4px;
  text-align: left;
}

.legend-item[aria-pressed="false"] {
  opacity: 0.35;
}

.swatch {
  width: 12px;
  height: 12px;
  flex: 0 0 auto;
}

.swatch.shape-ellipse { border-radius: 50%; }
.swatch.shape-rectangle { border-radius: 2px; }
.swatch.shape-diamond { transform: rotate(45deg); }

.empty-state {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  margin: 0;
  padding: 0 24px;
  text-align: center;
}

.drawer {
  border-top: 1px solid var(--border);
  max-height: 40vh;
  overflow-y: auto;
  padding: 12px 16px;
  background: var(--surface);
}

.drawer-close {
  float: right;
  border: none;
  background: none;
  font-size: 20px;
  cursor: pointer;
  color: var(--text);
}

.attr-table {
  border-collapse: collapse;
  width: 100%;
  font-size: 13px;
  margin: 8px 0;
}

.attr-table th, .attr-table td {
  text-align: left;
  padding: 4px 8px;
  border-bottom: 1px solid var(--border);
}

.attr-table th {
  color: var(--text-secondary);
  font-weight: 600;
  white-space: nowrap;
}

.case-text {
  line-height: 1.6;
  white-space: pre-wrap;
}

.case-text mark, .evidence-snippet {
  background: #eda100;
  color: #1a1a1a;
  padding: 0 2px;
}
```

- [ ] **Step 4: Verificar manualmente (sem `app.js` ainda, só o shell)**

```bash
cd project1/visualizer && python3 -m http.server 8000
```
Abra `http://localhost:8000/` no navegador. Expected: título "Grafo de Conhecimento — Casos Clínicos" no topo, campo de busca de caso ao lado, área abaixo vazia (sem abas, sem grafo — `app.js` ainda não existe, então o navegador mostra um erro 404 pra `app.js` no console, o que é esperado neste passo). Confirme que não há erro de carregamento do `cytoscape.min.js` (deve aparecer como carregado com sucesso nas ferramentas de rede do navegador). Pare o servidor (Ctrl+C) antes de continuar.

- [ ] **Step 5: Commit**

```bash
git add project1/visualizer/vendor/cytoscape.min.js project1/visualizer/index.html project1/visualizer/style.css
git commit -m "feat: monta shell estático do visualizador e vendoriza Cytoscape.js"
```

---

### Task 5: `app.js` — carregar dados, trocar de caso/aba, desenhar o grafo

**Files:**
- Create: `project1/visualizer/app.js`

**Interfaces:**
- Consumes: `project1/visualizer/data/manifest.json` e `project1/visualizer/data/<case_id>.json` (formato exato produzido por `export_all`, Task 2); ids do DOM da Task 4; `cytoscape` global (vendorizado, Task 4).
- Produces: funções internas reaproveitadas pela Task 6 (`openDrawer`, `closeDrawer`, `escapeHtml`, `state` global) — a Task 6 edita este mesmo arquivo, não cria um novo.

- [ ] **Step 1: Gerar dados reais pra testar contra (reusa a Task 2/3, já commitadas)**

```bash
python3 project1/tools/export_graph_data.py
```
Expected: `56 caso(s) exportado(s) para project1/visualizer/data` — esses arquivos ficam no working tree só para o teste manual desta e da próxima task; **não são commitados** (ver Global Constraints). Confirme que `.gitignore` já cobre isso ou adicione a entrada agora:
```bash
grep -q "^project1/visualizer/data/$" .gitignore || echo "project1/visualizer/data/" >> .gitignore
git add .gitignore
git commit -m "chore: ignora dados gerados do visualizador (só existem via CI/local)"
```

- [ ] **Step 2: Escrever `project1/visualizer/app.js` (carregamento, abas, grafo, legenda/filtro — sem gaveta de detalhes ainda)**

```javascript
"use strict";

const DATA_BASE = "data";

const NODE_STYLE = {
  Patient: { color: "#2a78d6", colorDark: "#3987e5", shape: "ellipse" },
  Symptom: { color: "#eb6834", colorDark: "#d95926", shape: "ellipse" },
  Exam: { color: "#1baf7a", colorDark: "#199e70", shape: "ellipse" },
  Finding: { color: "#eda100", colorDark: "#c98500", shape: "ellipse" },
  Diagnosis: { color: "#e87ba4", colorDark: "#d55181", shape: "ellipse" },
  Treatment: { color: "#008300", colorDark: "#008300", shape: "ellipse" },
  Medication: { color: "#4a3aa7", colorDark: "#9085e9", shape: "ellipse" },
  Outcome: { color: "#e34948", colorDark: "#e66767", shape: "ellipse" },
  History: { color: "#eb6834", colorDark: "#d95926", shape: "rectangle" },
  ExamResult: { color: "#1baf7a", colorDark: "#199e70", shape: "rectangle" },
  AnatomicalSite: { color: "#eda100", colorDark: "#c98500", shape: "rectangle" },
  Concept: { color: "#6b6b6b", colorDark: "#a3a3a3", shape: "diamond" },
};

const STRATEGY_LABELS = {
  combinado: "Combinado",
  tokenizacao: "Tokenização",
  stopwords: "Stopwords",
  dicionarios: "Dicionários",
  sintagmas: "Sintagmas",
  normalizacao: "Normalização",
};

const STRATEGY_ORDER = [
  "combinado",
  "tokenizacao",
  "stopwords",
  "dicionarios",
  "sintagmas",
  "normalizacao",
];

const state = {
  manifest: null,
  currentCase: null,
  currentCasePayload: null,
  currentStrategy: null,
  cy: null,
  hiddenTypes: new Set(),
};

function prefersDark() {
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function nodeColor(type) {
  const style = NODE_STYLE[type];
  if (!style) return "#999999";
  return prefersDark() ? style.colorDark : style.color;
}

function nodeShape(type) {
  const style = NODE_STYLE[type];
  return style ? style.shape : "ellipse";
}

async function fetchJson(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`falha ao carregar ${path}: ${response.status}`);
  }
  return response.json();
}

async function init() {
  state.manifest = await fetchJson(`${DATA_BASE}/manifest.json`);
  populateCaseOptions();
  document.getElementById("case-select").addEventListener("change", onCaseChange);
  document.getElementById("drawer-close").addEventListener("click", closeDrawer);
  window
    .matchMedia("(prefers-color-scheme: dark)")
    .addEventListener("change", () => {
      if (state.currentStrategy) {
        selectStrategy(state.currentStrategy);
      }
    });
  if (state.manifest.cases.length > 0) {
    const firstCaseId = state.manifest.cases[0].case_id;
    document.getElementById("case-select").value = firstCaseId;
    await loadCase(firstCaseId);
  }
}

function populateCaseOptions() {
  const datalist = document.getElementById("case-options");
  datalist.innerHTML = "";
  for (const entry of state.manifest.cases) {
    const option = document.createElement("option");
    option.value = entry.case_id;
    datalist.appendChild(option);
  }
}

async function onCaseChange(event) {
  const caseId = event.target.value.trim();
  const known = state.manifest.cases.some((entry) => entry.case_id === caseId);
  if (!known) return;
  await loadCase(caseId);
}

async function loadCase(caseId) {
  closeDrawer();
  state.currentCase = caseId;
  state.currentCasePayload = await fetchJson(`${DATA_BASE}/${caseId}.json`);
  renderTabs();
  const firstAvailable = STRATEGY_ORDER.find((key) => state.currentCasePayload.graphs[key]);
  if (firstAvailable) {
    selectStrategy(firstAvailable);
  } else {
    showEmptyState(true, "Nenhum grafo disponível para este caso.");
  }
}

function renderTabs() {
  const nav = document.getElementById("tabs");
  nav.innerHTML = "";
  for (const key of STRATEGY_ORDER) {
    const available = Boolean(state.currentCasePayload.graphs[key]);
    const button = document.createElement("button");
    button.textContent = STRATEGY_LABELS[key];
    button.className = "tab";
    button.disabled = !available;
    button.setAttribute("role", "tab");
    button.dataset.strategy = key;
    button.setAttribute("aria-selected", "false");
    if (available) {
      button.addEventListener("click", () => selectStrategy(key));
    }
    nav.appendChild(button);
  }
}

function selectStrategy(key) {
  state.currentStrategy = key;
  for (const button of document.querySelectorAll(".tab")) {
    button.setAttribute("aria-selected", String(button.dataset.strategy === key));
  }
  showEmptyState(false, "");
  renderGraph(state.currentCasePayload.graphs[key]);
}

function showEmptyState(show, message) {
  const emptyState = document.getElementById("empty-state");
  emptyState.hidden = !show;
  emptyState.textContent = message;
  document.getElementById("cy").hidden = show;
}

function renderGraph(graph) {
  if (state.cy) {
    state.cy.destroy();
    state.cy = null;
  }
  state.hiddenTypes = new Set();

  const elements = [
    ...graph.nodes.map((node) => ({
      data: { id: node.node_id, label: node.label, type: node.type, attributes: node.attributes },
    })),
    ...graph.edges.map((edge) => ({
      data: {
        id: edge.edge_id,
        source: edge.source_id,
        target: edge.target_id,
        relation: edge.relation,
        attributes: edge.attributes,
      },
    })),
  ];

  state.cy = cytoscape({
    container: document.getElementById("cy"),
    elements,
    style: [
      {
        selector: "node",
        style: {
          "background-color": (el) => nodeColor(el.data("type")),
          shape: (el) => nodeShape(el.data("type")),
          label: "data(label)",
          "font-size": 9,
          "text-wrap": "wrap",
          "text-max-width": "80px",
          width: 28,
          height: 28,
          color: "#1a1a1a",
          "text-valign": "bottom",
          "text-margin-y": 4,
        },
      },
      {
        selector: "edge",
        style: {
          width: 1.5,
          "line-color": "#999999",
          "target-arrow-color": "#999999",
          "target-arrow-shape": "triangle",
          "curve-style": "bezier",
          label: "data(relation)",
          "font-size": 7,
          color: "#666666",
        },
      },
      {
        selector: ".hidden-type",
        style: { display: "none" },
      },
    ],
    layout: { name: "cose", animate: false },
  });

  renderLegend(graph.nodes);
}

function renderLegend(nodes) {
  const legend = document.getElementById("legend");
  legend.innerHTML = "";
  const types = Array.from(new Set(nodes.map((node) => node.type))).sort();
  for (const type of types) {
    const item = document.createElement("button");
    item.className = "legend-item";
    item.dataset.type = type;
    item.setAttribute("aria-pressed", "true");
    const swatch = document.createElement("span");
    swatch.className = `swatch shape-${nodeShape(type)}`;
    swatch.style.backgroundColor = nodeColor(type);
    item.appendChild(swatch);
    item.appendChild(document.createTextNode(type));
    item.addEventListener("click", () => toggleType(type, item));
    legend.appendChild(item);
  }
}

function toggleType(type, legendItem) {
  if (state.hiddenTypes.has(type)) {
    state.hiddenTypes.delete(type);
    legendItem.setAttribute("aria-pressed", "true");
  } else {
    state.hiddenTypes.add(type);
    legendItem.setAttribute("aria-pressed", "false");
  }
  state.cy.nodes().forEach((node) => {
    node.toggleClass("hidden-type", state.hiddenTypes.has(node.data("type")));
  });
}

function openDrawer(html) {
  const drawer = document.getElementById("drawer");
  document.getElementById("drawer-body").innerHTML = html;
  drawer.hidden = false;
  const mark = document.getElementById("evidence-mark");
  if (mark) {
    mark.scrollIntoView({ block: "center" });
  }
}

function closeDrawer() {
  document.getElementById("drawer").hidden = true;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

init().catch((error) => {
  console.error(error);
  showEmptyState(true, `Erro ao carregar dados: ${error.message}`);
});
```

- [ ] **Step 3: Checar sintaxe**

Run: `node --check project1/visualizer/app.js`
Expected: sem saída (sucesso).

- [ ] **Step 4: Verificar manualmente no navegador**

```bash
cd project1/visualizer && python3 -m http.server 8000
```
Abra `http://localhost:8000/`. Expected:
- O campo de caso já vem preenchido com o primeiro `case_id` do manifesto (ordem alfabética) e o grafo dele aparece desenhado.
- As abas mostram `Combinado, Tokenização, Stopwords, Dicionários, Sintagmas, Normalização`; só as que existem pra aquele caso ficam clicáveis (as outras aparecem esmaecidas/desabilitadas).
- Digite `PMC5137649_01` no campo de caso e confirme (Enter ou clique fora): as 5 abas disponíveis (`Combinado, Tokenização, Stopwords, Dicionários, Normalização` — não `Sintagmas`) ficam habilitadas; clicar em cada uma redesenha o grafo.
- No canto superior direito do grafo, a legenda lista os tipos de nó presentes na aba atual, com uma marca colorida por tipo (círculo, quadrado ou losango conforme `NODE_STYLE`); clicar num item esconde/mostra os nós daquele tipo no grafo.
- Abra o console do navegador (F12) e confirme que não há erros JS.

Pare o servidor (Ctrl+C) antes de continuar. Apague a saída gerada no Step 1 se ainda não tiver feito:
```bash
rm -rf project1/visualizer/data
```

- [ ] **Step 5: Commit**

```bash
git add project1/visualizer/app.js
git commit -m "feat: carrega manifesto/caso e desenha o grafo com legenda/filtro por tipo"
```

---

### Task 6: Gaveta de detalhes — nó, aresta e evidência destacada no `case_text`

**Files:**
- Modify: `project1/visualizer/app.js` (adiciona funções e dois listeners; não remove nada da Task 5)

**Interfaces:**
- Consumes: `state.currentCasePayload.case_text` (pode não existir — degradação), `openDrawer`/`closeDrawer`/`escapeHtml`/`state` (Task 5).

- [ ] **Step 1: Adicionar os listeners de clique em nó/aresta dentro de `renderGraph`**

Em `project1/visualizer/app.js`, dentro de `renderGraph`, logo depois de `state.cy = cytoscape({...});`, adicione (antes da chamada a `renderLegend(graph.nodes);`):

```javascript
  state.cy.on("tap", "node", (event) => showNodeDetails(event.target.data()));
  state.cy.on("tap", "edge", (event) => showEdgeDetails(event.target.data()));
```

- [ ] **Step 2: Adicionar as funções de detalhe, no final do arquivo, antes da chamada `init().catch(...)`**

```javascript
function showNodeDetails(data) {
  const rows = Object.entries(data.attributes || {})
    .map(([key, value]) => `<tr><th>${escapeHtml(key)}</th><td>${escapeHtml(value)}</td></tr>`)
    .join("");
  openDrawer(`
    <h2>${escapeHtml(data.type)}</h2>
    <p class="drawer-label">${escapeHtml(data.label)}</p>
    <table class="attr-table"><tbody>${rows}</tbody></table>
  `);
}

function showEdgeDetails(data) {
  const attrs = data.attributes || {};
  const rows = Object.entries(attrs)
    .filter(([key]) => !["evidence_text", "char_start", "char_end"].includes(key))
    .map(([key, value]) => `<tr><th>${escapeHtml(key)}</th><td>${escapeHtml(value)}</td></tr>`)
    .join("");

  openDrawer(`
    <h2>${escapeHtml(data.relation)}</h2>
    <table class="attr-table"><tbody>${rows}</tbody></table>
    <h3>Evidência</h3>
    ${buildEvidenceHtml(attrs)}
  `);
}

function buildEvidenceHtml(attrs) {
  const caseText = state.currentCasePayload.case_text;
  const start = Number.parseInt(attrs.char_start, 10);
  const end = Number.parseInt(attrs.char_end, 10);
  const hasSpan =
    caseText && Number.isFinite(start) && Number.isFinite(end) && end > start && end <= caseText.length;

  if (!hasSpan) {
    return `<p class="evidence-snippet">"${escapeHtml(attrs.evidence_text || "")}"</p>`;
  }

  const before = escapeHtml(caseText.slice(0, start));
  const span = escapeHtml(caseText.slice(start, end));
  const after = escapeHtml(caseText.slice(end));
  return `<p class="case-text">${before}<mark id="evidence-mark">${span}</mark>${after}</p>`;
}
```

Note que `buildEvidenceHtml` cobre a degradação da spec (caso sem `case_text`, ou aresta sem offset, ou offset inválido) caindo para mostrar só `evidence_text` entre aspas.

- [ ] **Step 3: Checar sintaxe**

Run: `node --check project1/visualizer/app.js`
Expected: sem saída (sucesso).

- [ ] **Step 4: Verificar manualmente com um caso completo e um caso parcial**

```bash
python3 project1/tools/export_graph_data.py
cd project1/visualizer && python3 -m http.server 8000
```
Abra `http://localhost:8000/` e selecione `PMC5137649_01` (tem `case_text` + todas as estratégias exceto sintagmas):
- Clique num nó (círculo/quadrado/losango) qualquer: a gaveta abre embaixo com o tipo, o `label` e uma tabela de atributos.
- Clique numa aresta: a gaveta mostra a relação, os atributos (exceto `evidence_text`/`char_start`/`char_end`, que já viram o texto destacado), e abaixo o `case_text` inteiro com o trecho de evidência realçado (fundo amarelo) e a rolagem já centralizada nele.
- Clique no `×` da gaveta: ela fecha.
- Troque de caso (ex.: digite `PMC10106591_01`, que só tem `dicionarios`+`stopwords`, sem `case_text` em `case_texts.csv`... na verdade **todos** os 56 casos têm `case_text` desde a Task 3; para testar a degradação de verdade, edite temporariamente `project1/visualizer/data/PMC10106591_01.json` removendo a chave `"case_text"` e recarregue a página) e clique numa aresta: a gaveta deve mostrar só o `evidence_text` entre aspas, sem quebrar.
- Desfaça a edição manual do JSON de teste (ou rode `python3 project1/tools/export_graph_data.py` de novo para regenerar do zero).

Pare o servidor e apague a saída gerada:
```bash
rm -rf project1/visualizer/data
```

- [ ] **Step 5: Commit**

```bash
git add project1/visualizer/app.js
git commit -m "feat: adiciona gaveta de detalhes com evidência destacada no case_text"
```

---

### Task 7: Deploy (GitHub Actions + Pages) e link no README

**Files:**
- Create: `.github/workflows/deploy-visualizer.yml`
- Create: `project1/visualizer/README.md`
- Modify: `project1/README.md` (adiciona link para o site publicado)

**Interfaces:**
- Consumes: `python3 project1/tools/export_graph_data.py` (Task 2/3), `project1/visualizer/` inteiro (Tasks 4–6).

- [ ] **Step 1: Criar `.github/workflows/deploy-visualizer.yml`**

```yaml
name: Deploy Visualizer

on:
  push:
    branches: [main]
    paths:
      - "project1/data/**"
      - "project1/src/*/output/**"
      - "project1/visualizer/**"
      - "project1/tools/**"
  workflow_dispatch: {}

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Gerar dados do visualizador
        run: python3 project1/tools/export_graph_data.py
      - uses: actions/upload-pages-artifact@v3
        with:
          path: project1/visualizer

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: Validar a sintaxe do YAML**

Run:
```bash
python3 -m venv /tmp/yamlcheck && /tmp/yamlcheck/bin/pip install --quiet pyyaml && \
  /tmp/yamlcheck/bin/python -c "import yaml; yaml.safe_load(open('.github/workflows/deploy-visualizer.yml')); print('YAML OK')" && \
  rm -rf /tmp/yamlcheck
```
Expected: `YAML OK`.

- [ ] **Step 3: Criar `project1/visualizer/README.md`**

```markdown
# Visualizador de Grafos — `project1`

Site estático (HTML/JS puro + [Cytoscape.js](https://js.cytoscape.org/), vendorizado
em `vendor/cytoscape.min.js`, sem CDN nem bundler) que mostra o grafo de conhecimento
de cada caso da amostra: o grafo combinado final e o grafo de cada estratégia isolada
(tokenização, stopwords, dicionários, sintagmas, normalização).

## Rodar localmente

Precisa dos dados gerados em `data/` primeiro (não são commitados — ver `.gitignore`):

```bash
python3 ../tools/export_graph_data.py   # a partir de project1/visualizer/
cd .. && python3 -m http.server 8000 --directory visualizer
```

Abra `http://localhost:8000/`.

## Como os dados chegam aqui

`tools/export_graph_data.py` lê `data/processed/` (grafo combinado) e cada
`src/<estrategia>/output/` (grafo por estratégia), casando pelo `case_id`, e escreve
um JSON por caso + `manifest.json` em `visualizer/data/`. Roda sozinho a cada push
relevante via `.github/workflows/deploy-visualizer.yml`; localmente, rode manualmente
como acima sempre que quiser ver dados atualizados.

## `case_texts.csv`

A gaveta de detalhes mostra o `case_text` completo com o trecho de evidência
destacado. Como `sample/` não é versionado, esse texto vem de
`project1/data/case_texts.csv` (`case_id`, `case_text`), um recorte comitado
especificamente para isso. Se a amostra local mudar (novos casos, texto corrigido),
regenere e recommite:

```bash
python3 ../tools/generate_case_texts.py   # a partir de project1/visualizer/, precisa de sample/cases.csv local
```

## Habilitar o GitHub Pages (uma vez, manual)

Em Settings → Pages do repositório, em "Build and deployment", escolha
**Source: GitHub Actions**. Depois disso, todo push em `main` que toque
`project1/data/**`, `project1/src/*/output/**`, `project1/visualizer/**` ou
`project1/tools/**` publica o site automaticamente (ver o workflow
`deploy-visualizer.yml`).
```

- [ ] **Step 4: Adicionar link no `project1/README.md`**

Leia o arquivo atual antes de editar (`project1/README.md`). Adicione, logo depois da seção `## Slides` (linhas 3–5 hoje):

```markdown
## Visualizador

[Grafos interativos por caso](https://caiomelloni.github.io/PNL-CGGJL/) — combinado e
por estratégia, com auditoria de evidência contra o `case_text` original
([`project1/visualizer/`](visualizer/)).
```

Ajuste a URL se o Pages publicar em outro caminho (confirme em Settings → Pages depois do primeiro deploy bem-sucedido).

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/deploy-visualizer.yml project1/visualizer/README.md project1/README.md
git commit -m "feat: publica o visualizador no GitHub Pages via Actions"
```

- [ ] **Step 6: Habilitar o Pages manualmente e confirmar o primeiro deploy**

Isso não é um passo de código — é uma ação no site do GitHub que só quem tem permissão de admin no repositório pode fazer, então **não deve ser automatizado**: em Settings → Pages, em "Build and deployment", escolha "Source: GitHub Actions". Depois de dar push nos commits desta task para `main`, confira em Actions que o workflow `Deploy Visualizer` rodou com sucesso, e abra a URL publicada (aparece em Settings → Pages) para confirmar que o site carrega e mostra `PMC5137649_01` com todas as abas esperadas.
