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

Também lê `project2/data/grafo/` (saída de `project2/src/montagem/montagem.py`), caso exista,
expondo-a como a aba "Projeto 2". Quando um caso tem tanto esse grafo quanto o grafo combinado do
Projeto 1, o combinado passa a aparecer com o rótulo "Projeto 1" no lugar de "Combinado" (mesmo
grafo, renomeado, não duplicado) para facilitar a comparação lado a lado — casos sem grafo do
Projeto 2 continuam mostrando "Combinado" normalmente. Hoje o `.gitignore` do repositório só
versiona `project2/data/grafo/PMC5137649_01-*.csv`; os demais casos ficam de fora até que a
montagem do Projeto 2 gere (e alguém decida commitar) mais grafos — por isso só esse caso mostra
a aba "Projeto 2" no site publicado.

O leitor compartilhado `tools/graph_csv.py` aceita tanto os atributos legados `chave=valor`
quanto objetos JSON com valores string. O serializador da tokenização e da montagem P2 usa
JSON quando texto como `CT; p=0.05` tornaria o formato legado ambíguo.

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
