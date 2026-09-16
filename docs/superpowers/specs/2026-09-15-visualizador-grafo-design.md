# Design — Visualizador interativo do grafo de conhecimento por caso (issue #20)

> Não é uma issue de estratégia de extração (#3–#9): consome os CSVs de nós/arestas que essas
> issues e o pipeline combinado (`pipelines/notebooks/grafo_combinado.ipynb`) já produzem. O
> contrato de dados (`docs/01-dados-a-extrair.md`, `docs/02-esquema-grafo.md`) não muda.

## Objetivo

Dar ao professor um jeito de abrir, a partir do repositório no GitHub, o grafo de conhecimento
gerado para qualquer caso da amostra — tanto o grafo combinado final quanto o grafo de cada
estratégia isolada (tokenização, stopwords, dicionários, sintagmas, normalização) — navegável,
filtrável por tipo de nó, e com cada aresta auditável contra o texto original do caso.

## Fora de escopo

- Diff/comparação automática entre abas (nó "adicionado/removido" entre estratégias). Cada aba
  redesenha seu grafo isoladamente; a comparação é visual, feita pelo professor.
- Busca de casos por conceito/diagnóstico entre os 56 casos. Só navegação por `case_id`.
- Qualquer edição do grafo pela interface (é só leitura).
- Mudar o pipeline combinado ou os parsers de estratégia — o visualizador é consumidor dos CSVs
  que eles já exportam, hoje (1 caso combinado, 56 por estratégia) e conforme crescerem.
- Framework JS com bundler (React/Vite) — HTML/JS puro, ver "Site" abaixo.

## Bloqueio de dados encontrado e decisão

`sample/` (que tem o `case_text` completo) está no `.gitignore` do repositório ("amostra da
disciplina — não versionada"). Um runner de GitHub Actions faz checkout do repositório, não tem
acesso a `sample/`. Como a gaveta de detalhes precisa mostrar o `case_text` completo com o trecho
de evidência destacado (não só o `evidence_text` isolado), é preciso versionar um recorte mínimo:

- Novo arquivo `project1/data/case_texts.csv` (colunas: `case_id`, `case_text`), gerado a partir de
  `sample/cases.csv` e commitado especificamente para o visualizador.
- `sample/` continua fora do git como hoje — `metadata.csv`, autores, DOIs etc. não são
  necessários para o visualizador e não são versionados.
- Consequência prática: sempre que a amostra mudar (novos casos, texto corrigido), alguém com
  `sample/cases.csv` local precisa regerar `case_texts.csv` e commitar. É manual, documentado no
  README do visualizador — não é um script que já roda em CI, porque CI não tem `sample/`.

## Arquitetura

```
project1/
  data/
    case_texts.csv              # NOVO — case_id, case_text (recorte versionado de sample/cases.csv)
    processed/                  # já existe — grafo combinado, hoje só PMC5137649_01
  src/
    dicionarios/output/         # já existe — 56 casos
    stopwords/output/           # já existe — 56 casos
    tokenizacao/output/         # já existe — só o caso de exemplo (PMC5137649_01) hoje
    normalizacao/output/        # já existe — só o caso de exemplo (PMC5137649_01) hoje
    sintagmas/                  # sem output/ hoje — ver nota abaixo
  tools/
    export_graph_data.py        # NOVO — CSVs -> JSON consumido pelo site
  visualizer/
    index.html                  # NOVO
    app.js
    style.css
    vendor/cytoscape.min.js     # vendorizado, sem CDN
    README.md                   # como rodar localmente e como regenerar case_texts.csv
.github/
  workflows/
    deploy-visualizer.yml       # NOVO
```

**Nota sobre `sintagmas` e cobertura parcial**: hoje `sintagmas/` não tem pasta `output/` nem
`<case_id>-nodes.csv`/`-edges.csv` — o próprio `src/sintagmas/README.md` diz que a etapa exporta
CoNLL/IOB2 e que "montar o grafo é etapa seguinte", ainda não feita. `tokenizacao/output/` e
`normalizacao/output/` também só têm o caso de exemplo (`PMC5137649_01`) versionado, não os 56.
Isso não é um problema do visualizador: `export_graph_data.py` só lista uma aba de estratégia
quando encontra `<case_id>-nodes.csv` + `-edges.csv` naquela pasta para aquele `case_id` — hoje
isso dá zero abas de `sintagmas` em qualquer caso, e uma aba de `tokenizacao`/`normalizacao` só em
`PMC5137649_01`. O manifesto (e a UI, com abas desabilitadas) reflete exatamente essa cobertura
real e cresce sozinho conforme cada estratégia publicar mais casos — nenhuma mudança no
visualizador é necessária quando isso acontecer.

### `export_graph_data.py`

Para cada `case_id` encontrado em `data/processed/` ou em qualquer `src/*/output/`:

1. Lê `case_texts.csv` → `case_text` (se o `case_id` não estiver lá, o caso é exportado sem texto
   e a gaveta de detalhes cai para mostrar só `evidence_text`, ver "Degradação sem case_text").
2. Lê `<case_id>-nodes.csv` / `<case_id>-edges.csv` de cada fonte disponível (combinado +
   estratégias), na forma do contrato comum (`case_id, node_id, type, label, attributes` /
   `case_id, edge_id, source_id, target_id, relation, attributes`), e reserializa `attributes`
   (hoje `chave=valor; chave=valor`) como objeto JSON.
3. Escreve `project1/visualizer/data/<case_id>.json`:
   ```json
   {
     "case_id": "PMC5137649_01",
     "case_text": "A 44-year-old woman presented with...",
     "graphs": {
       "combinado": { "nodes": [...], "edges": [...] },
       "tokenizacao": { "nodes": [...], "edges": [...] }
     }
   }
   ```
   Só as chaves de `graphs` com dado disponível para aquele caso aparecem.
4. Escreve `project1/visualizer/data/manifest.json`: lista de `case_id` com as chaves de `graphs`
   disponíveis em cada um — alimenta o dropdown de caso e quais abas ficam habilitadas.

Script Python (consistente com o resto do repo), sem dependências além da biblioteca padrão —
mesma restrição das estratégias de extração.

## Site

HTML/JS puro, Cytoscape.js vendorizado (um arquivo local, sem bundler nem CDN). Layout:

- **Barra superior**: seletor de caso (dropdown pesquisável, populado do `manifest.json`) + abas
  por grafo disponível para aquele caso (`Combinado`, `Tokenização`, `Stopwords`, `Dicionários`,
  `Sintagmas`, `Normalização`); aba sem dado para o caso atual aparece desabilitada, não escondida
  (deixa claro que a estratégia existe mas não gerou saída pra aquele caso).
- **Canvas central**: grafo da aba ativa renderizado com Cytoscape.js, layout de força
  (`cose`/`fcose`) — grafos por caso são pequenos (dezenas de nós, não centenas), não precisa de
  virtualização.
- **Legenda/filtro** (canto do canvas, recolhível): um item por tipo de nó presente no grafo atual,
  cor + nome do tipo; clicar num item alterna a visibilidade daquele tipo no canvas. Filtro
  reconstrói a cada troca de aba/caso a partir dos tipos realmente presentes.
- **Gaveta inferior de detalhes**: fechada por padrão, abre ao clicar num nó ou aresta.
  - Nó: tipo, label, tabela de atributos.
  - Aresta: relação, trigger, certainty, e — quando o caso tem `case_text` — o texto completo do
    caso com o trecho `[char_start:char_end]` destacado e centralizado na rolagem da gaveta.
  - **Degradação sem `case_text`** (caso ausente de `case_texts.csv`): mostra só `evidence_text`
    isolado, sem o texto completo — mesma informação que já está no CSV de arestas, sem quebrar a
    gaveta.

## Codificação visual

- Cor por tipo de nó: as 8 cores categóricas validadas por padrão pelo
  `scripts/validate_palette.js` do skill `dataviz` (ordem fixa; adjacent-pair PASS em claro e
  escuro). Para as 12 categorias reais do contrato (11 entidades clínicas + `Concept`), inventar
  4 cores extras não passou de forma robusta na validação (ΔE de visão normal ficou na borda do
  piso, 14–16 contra o mínimo de 15, em várias tentativas) — em vez disso, a identidade combina
  **cor + forma**: 8 tipos com cor única (elipse), 3 tipos reaproveitam a cor de um tipo
  clinicamente relacionado mas em forma de retângulo (`History`↔`Symptom`, `ExamResult`↔`Exam`,
  `AnatomicalSite`↔`Finding`), e `Concept` (âncora de vocabulário controlado, não entidade
  clínica) fica em cinza neutro + losango, fora da paleta categórica. Cor nunca é o único sinal:
  todo nó também mostra o tipo como texto no rótulo/tooltip.
- Arestas em cinza neutro, sem cor por relação. O nome da relação só aparece sob interação
  (hover/click) — não há legenda de cor para aresta.
- Tema claro/escuro do site segue o esquema do sistema do professor (`prefers-color-scheme`), sem
  alternância manual — YAGNI para um dashboard de uso pontual.

## Deploy (GitHub Pages)

`.github/workflows/deploy-visualizer.yml`:

- Dispara em push para `main` que toque `project1/data/**`, `project1/src/*/output/**` ou
  `project1/visualizer/**` (mais `workflow_dispatch` manual).
- Roda `export_graph_data.py`, gera `project1/visualizer/data/*.json`.
- Publica `project1/visualizer/` (site estático + dados gerados) via `actions/upload-pages-artifact`
  + `actions/deploy-pages` — deploy oficial do GitHub Pages, nada de artefato gerado é commitado em
  nenhum branch.
- `project1/README.md` ganha um link para a URL publicada ("Ver grafos interativos: ...").

## Erros e casos de borda

- **Caso sem nenhum grafo** (não deveria acontecer, mas o manifesto é gerado por varredura de
  diretório): não aparece no dropdown.
- **`attributes` vazio ou mal formado** numa linha do CSV: nó/aresta é exportado com
  `attributes: {}`, não quebra a exportação nem o render.
- **CSV de uma estratégia ausente para um caso** (ex.: `sintagmas` não processou aquele caso):
  chave correspondente simplesmente não existe em `graphs` — já coberto pela aba desabilitada.
- **`case_texts.csv` desatualizado** (novo caso na amostra sem entrada correspondente): caso é
  exportado, gaveta cai para `evidence_text` isolado (ver "Degradação sem case_text"); não é
  tratado como erro fatal do build.

## Testes

- `export_graph_data.py`: testes unitários (`unittest`, como o resto do repo) cobrindo parsing de
  `attributes` (`chave=valor; chave=valor` → dict), montagem do manifesto com fontes parciais
  (caso só em `tokenizacao/output`, caso em `data/processed` + duas estratégias) e o caso sem
  entrada em `case_texts.csv`.
- Front-end: sem framework de teste automatizado (site pequeno, somem-se ao padrão do restante do
  projeto, que não testa notebooks/visualizações). Verificação manual: abrir o site localmente
  (servidor estático simples) e navegar por pelo menos um caso com todas as abas populadas
  (`PMC5137649_01`, hoje o único com grafo combinado) e um caso só com estratégias isoladas, antes
  de considerar a issue concluída.
