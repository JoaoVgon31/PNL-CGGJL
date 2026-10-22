# Design — Grafos do Projeto 2 no visualizador do Projeto 1

> Depende do visualizador existente (`docs/superpowers/specs/2026-09-15-visualizador-grafo-design.md`)
> e do contrato CSV comum que `project2/src/montagem/montagem.py` já produz (mesmo formato de
> `project1/tools/graph_csv.py`). Não é uma mudança de pipeline de extração do Projeto 2 — só de
> como o grafo que ele já exporta chega ao site publicado.

## Objetivo

Fazer o site publicado no GitHub Pages (`project1/visualizer/`) mostrar, para cada caso que tiver
grafo gerado pelo Projeto 2, abas de comparação "Projeto 1" / "Projeto 2" lado a lado com as abas
de estratégia já existentes — sem exigir um passo manual separado.

## Estado atual (o que já existe e não muda)

- `project1/visualizer/app.js` já sabe renderizar abas `projeto1`/`projeto2` (`STRATEGY_LABELS`,
  `STRATEGY_ORDER`) e já esconde a aba `combinado` quando `projeto2` está presente no payload do
  caso (`renderTabs`). Isso foi adicionado para servir a cópia standalone descrita abaixo; nenhuma
  mudança de front-end é necessária aqui.
- `project2/src/montagem/montagem.py --visualizador <dir>` copia `project1/visualizer/` para um
  diretório separado e gera `<dir>/data/*.json` já com as chaves `projeto1`/`projeto2`, lendo
  `project2/data/grafo/` (saída da própria montagem) e `project1/data/processed/` (via
  `--p1-grafos`, default já é esse caminho). Continua existindo, para demos locais/sintéticas
  (`project2/experimentos/demo/`) independentes do site publicado — fora de escopo mudar.
- `project1/tools/export_graph_data.py` — o script que de fato gera os dados do site
  publicado — hoje **não lê `project2/data/grafo/`**. É a lacuna que este spec fecha.

## Bloqueio de dados encontrado

`project2/data/grafo/` está no `.gitignore`, exceto por um caso:

```
project2/data/grafo/*
!project2/data/grafo/PMC5137649_01-*.csv
```

Hoje só esse caso tem grafo do Projeto 2 commitado (o gabarito de avaliação,
`project2/data/gold/casos.txt`, tem 8 casos; a montagem completa para todos eles depende de
`mencoes_tipadas.csv`, que não está versionado e não está presente localmente agora). Isso não
bloqueia este spec: a integração é dirigida pelo conteúdo real de `project2/data/grafo/` e cresce
sozinha conforme mais grafos forem gerados e commitados — igual ao padrão já usado para
`tokenizacao`/`normalizacao`/`sintagmas` no visualizador original.

## Arquitetura

```
project1/
  tools/
    export_graph_data.py        # MUDA — nova fonte "projeto2" + alias "projeto1"
    tests/
      test_export_graph_data.py # MUDA — cobre a fonte nova e o alias
  visualizer/
    README.md                   # MUDA — documenta a fonte nova
    app.js                       # inalterado
project2/
  data/
    grafo/                       # fonte lida pela nova entrada em STRATEGY_SOURCES
.github/
  workflows/
    deploy-visualizer.yml       # MUDA — novo path de trigger
```

### `export_graph_data.py`

1. **Nova fonte em `STRATEGY_SOURCES`**: `"projeto2": Path("../project2/data/grafo")` — caminho
   relativo à raiz de `project1/` (`PROJECT_ROOT`), no mesmo padrão das outras entradas. `project2/`
   é diretório-irmão de `project1/` no repositório, então `PROJECT_ROOT / "../project2/data/grafo"`
   resolve corretamente para `<repo>/project2/data/grafo`. `discover_cases` não muda — já trata
   cada entrada de `STRATEGY_SOURCES` de forma independente e tolera diretório ausente.

2. **Alias `projeto1` em `build_case_payload`**: depois de montar o dict `graphs` a partir das
   fontes descobertas para o caso, se `"projeto2"` e `"combinado"` estiverem ambos presentes,
   adicionar `graphs["projeto1"] = graphs["combinado"]` (mesmo objeto, sem reler CSV). Efeito:
   - Caso **sem** grafo do Projeto 2: comportamento idêntico ao atual (só `combinado` +
     estratégias disponíveis).
   - Caso **com** grafo do Projeto 2: ganha as chaves `projeto1` (alias de `combinado`) e
     `projeto2`; a UI já existente esconde a aba `Combinado` e mostra `Projeto 1`/`Projeto 2` no
     lugar, mantendo as abas de estratégia isolada (`Tokenização`, `Stopwords`, etc.) como estão.
   - Isso evita duplicar uma aba `Projeto 1` idêntica a `Combinado` nos casos (a maioria, hoje)
     sem contraparte em P2 — decisão tomada no brainstorming, não é comportamento implícito do
     front-end.

3. **`build_manifest`**: sem mudança de código — já reflete `sorted(graphs.keys())`, que agora pode
   incluir `projeto1`/`projeto2` quando aplicável.

Nenhuma mudança em `read_nodes_csv`/`read_edges_csv` (`graph_csv.py`): o CSV de saída de
`montagem.py` já segue o mesmo contrato (`case_id, node_id, type, label, attributes` /
`case_id, edge_id, source_id, target_id, relation, attributes`, `attributes` em `chave=valor` ou
JSON), confirmado pelos arquivos reais em `project2/data/grafo/PMC5137649_01-*.csv`.

## Deploy (GitHub Pages)

`.github/workflows/deploy-visualizer.yml` ganha `"project2/data/grafo/**"` na lista de `paths` do
trigger `push`, ao lado dos paths de `project1/` já existentes. Sem outra mudança no workflow: o
`actions/checkout@v4` já traz o repositório inteiro, incluindo `project2/`, e o job já roda
`python3 project1/tools/export_graph_data.py` a partir da raiz do repo.

## Erros e casos de borda

- **Caso com `projeto2` mas sem `combinado`** (Projeto 2 processou um caso fora da amostra do
  Projeto 1, ou `project1/data/processed/` ainda não tem esse caso): fica só com a aba
  `Projeto 2`, sem alias `projeto1` — não é tratado como erro.
- **Caso com `combinado` mas sem `projeto2`** (situação atual de quase todos os casos): nenhuma
  mudança visível — continua mostrando `Combinado` normalmente.
- **`project2/data/grafo/` ausente** (ex.: checkout parcial, ambiente local sem o diretório):
  `discover_cases` já tolera fonte ausente (mesmo tratamento das outras estratégias) — não quebra
  a exportação.

## Testes

- `project1/tools/tests/test_export_graph_data.py`:
  - `discover_cases` com layout de diretórios-irmãos (`<tmp>/project1`, `<tmp>/project2/data/grafo`)
    confirmando que a chave `projeto2` é descoberta a partir da raiz de `project1`.
  - `build_case_payload` com `sources` incluindo `projeto2` + `combinado`: confirma
    `graphs["projeto1"] == graphs["combinado"]`.
  - `build_case_payload` com `sources` só `projeto2` (sem `combinado`) e só `combinado` (sem
    `projeto2`): confirma que `projeto1` **não** é adicionado em nenhum dos dois casos.
  - Atualizar/estender o teste de integração de `export_all` se o layout de diretórios-irmãos for
    necessário para cobrir o fluxo completo.
- Front-end: verificação manual (sem framework de teste, igual ao visualizador original) — rodar
  `export_graph_data.py` localmente, servir `project1/visualizer/` e confirmar que o caso
  `PMC5137649_01` mostra as abas `Projeto 1`/`Projeto 2` (não `Combinado`), que o conteúdo da aba
  `Projeto 1` é idêntico ao `Combinado` de antes, e que outro caso qualquer sem grafo do Projeto 2
  continua mostrando `Combinado` normalmente.

## Fora de escopo

- Mudar `montagem.py` ou o modo `--visualizador` standalone.
- Gerar/commitar mais casos em `project2/data/grafo/` — depende do pipeline de montagem do
  Projeto 2 (lacuna de integração já registrada separadamente), não deste spec.
- Diff visual entre o grafo do Projeto 1 e do Projeto 2 (nó/aresta "só em P2", por exemplo) — cada
  aba continua renderizando seu grafo isoladamente, igual às demais.
- Mudar o trigger do workflow para rodar `montagem.py` em CI — hoje os grafos do Projeto 2 chegam
  ao repositório só por commit manual (mesma política da exceção no `.gitignore`).
