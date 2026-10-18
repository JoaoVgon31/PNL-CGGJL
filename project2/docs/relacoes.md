# Etapa 4 — Relações entre entidades: decisão e resultados

> Entregável da [issue #35](https://github.com/caiomelloni/PNL-CGGJL/issues/35) — Projeto 2 (MC896, 2026).
> Código em [`project2/src/relacoes/`](../src/relacoes/) (como rodar: [`README.md`](../src/relacoes/README.md)).
> Gerador de dados em [`project2/src/relacoes/mock/`](../src/relacoes/mock/).

## Contexto

O Projeto 1 extrai relações clínicas (`HAS_SYMPTOM`, `LOCATED_IN`, `DIAGNOSED_WITH`...) por regras
fixas. A hipótese desta issue é que um classificador estatístico, treinado sobre N-gramas do texto
entre duas entidades, consegue generalizar melhor para os casos que as regras não cobrem — sem usar
LLM, embeddings ou modelo de linguagem baseado em Transformers (restrição do Projeto 2). Este
documento não assume essa hipótese: mede o que aconteceu ao combinar as duas abordagens.

## A decisão de arquitetura: regra onde é determinístico, classificador onde não é

Nem toda relação precisa de aprendizado. Quando um dos lados do par é o `Patient`, o tipo do outro
lado já determina a relação sem ambiguidade (`Patient+Symptom = HAS_SYMPTOM`,
`Patient+Exam = UNDERWENT_EXAM`, etc. — tabela completa em `PATIENT_RELATION_MAP`,
[`relacoes.py`](../src/relacoes/relacoes.py)). Só as relações entre duas entidades não-`Patient`
(`REVEALS`, `LOCATED_IN`, `HAS_RESULT`, `SUPPORTS`) dependem de contexto textual real, e são essas
que o classificador de N-gramas (TF-IDF sobre o texto entre as entidades + tipos + distância + ordem,
`LogisticRegression`/`LinearSVC`) resolve.

## O problema da v1 e a correção medida da v2

A primeira tentativa desta etapa dependia de um script de outro colega que casava o texto de cada
menção contra o `label` salvo pelo Projeto 1 nos nós do grafo — e esse `label` às vezes vem
consolidado/reescrito, não bate literalmente com o texto bruto. Medido: **38% dos casos de
treino/validação e 75% dos casos de teste** ficavam sem nenhuma relação não-`NONE` por causa desse
casamento frágil — não porque a relação não existisse no texto, mas porque o script não conseguia
"costurar" o trecho certo com o nó certo.

A correção não foi ajustar o casamento de texto — foi abandoná-lo. O `edges.csv` do Projeto 1 já
exporta `char_start`/`char_end` da evidência de cada relação (campo `attributes`), ignorado pelo
script antigo. O gerador desta v2 (`project2/src/relacoes/mock/gerar.py`) resolve cada relação
contra uma menção real via **sobreposição de offset de caractere + tipo** — nunca por texto. Medido
nos dados reais (56 casos, 51 elegíveis depois de reservar 5 casos de gabarito): de 842 arestas
clínicas do Projeto 1 com offset de evidência, **599 foram resolvidas, 62 descartadas** (nenhuma
menção do tipo certo caiu na janela de evidência) **e 181 colapsadas** por deduplicação (duas
arestas do Projeto 1 apontando para o mesmo par de menções — verificado que nunca têm rótulos
conflitantes, então não geram dado errado, só reduzem a contagem). Perda real de cobertura:
(62+181)/842 ≈ **28,6%** — bem menor que os 38–75% da v1, e sem nenhum casamento por texto residual.

## Resultado agregado — grid de 4 configurações em `val`, vencedora avaliada em `test`

(gerado por `python3 -m project2.src.relacoes.relacoes`; tabela completa em
[`project2/data/resultados/relacoes.csv`](../data/resultados/relacoes.csv).)

| Modelo | N-grama | Split | macro-F1 (sem `NONE`) |
|---|---|---|---:|
| LogisticRegression | 1-1 | val | 0,691 |
| LogisticRegression | 1-3 | val | 0,688 |
| LinearSVC | 1-1 | val | **0,761** |
| LinearSVC | 1-3 | val | 0,757 |
| LogisticRegression | 1-1 (vencedora) | test | 0,480 |

`LinearSVC` vence o grid em `val`, mas **nunca gera a predição final** — só `LogisticRegression`
fornece `predict_proba` nativo para a coluna `confidence` das predições de produção
(`select_best_lr_config` só compara as duas variantes de n-grama da regressão logística entre si).
Entre `1-1` e `1-3`, `1-1` venceu por uma margem pequena (0,691 vs 0,688) — ver ressalva abaixo sobre
quão poucas amostras sustentam essa escolha.

## Discussão por tipo de relação

| Relação | Precision (val) | Recall (val) | Suporte (val) | Suporte (test) |
|---|---:|---:|---:|---:|
| `HAS_RESULT` | 0,41 | 1,00 | 20 | 14 |
| `LOCATED_IN` | 0,88 | 1,00 | 15 | 13 |
| `REVEALS` | 0,39 | 1,00 | 5 | 3 |
| `SUPPORTS` | — | — | **0** | 2 |
| `NONE` | 1,00 | 0,86 | 275 | 523 |

**O classificador erra para o lado de "achar relação demais", nunca para o lado de perder uma
relação real.** Recall 1,00 em quase toda relação não-`NONE`, mas precisão baixa (0,39–0,41 em
`HAS_RESULT`/`REVEALS`): na matriz de confusão de `val`, 29 pares que eram `NONE` de verdade foram
classificados como `HAS_RESULT`, 8 como `REVEALS`. Isso é efeito direto de treinar com
`class_weight="balanced"` sobre um conjunto ~90% `NONE` — o modelo compensa o desbalanço penalizando
mais perder uma relação rara do que gerar um falso positivo. Para o relatório, isso é uma
característica do método, não um bug: vale reportar como trade-off (prioriza recall sobre precisão
nas classes raras).

**`SUPPORTS` não tem exemplo nenhum em `val`.** Só 5 ocorrências em todo o corpus de 56 casos (3 em
treino, 0 em val, 2 em teste) — a relação (achado/sintoma → diagnóstico com marcador textual como
*"consistent with"*, *"suggesting"*) é genuinamente rara nos 56 casos da amostra, não um defeito de
extração. Consequência prática: a escolha entre `1-1` e `1-3` grama em `select_best_lr_config` foi
decidida por uma margem de 0,003 sobre um macro-F1 calculado com uma classe de suporte zero — uma
decisão estatisticamente frágil, não um resultado robusto.

**A regra do paciente nunca vê um exemplo negativo.** De 432 pares envolvendo `Patient` nos dados
gerados, 432 são positivos e 0 são `NONE` — o gerador nunca cria um candidato negativo em que
`Patient` participa, porque a regra resolve esses pares por tipo, não por classificação. Uma
conclusão de relatório do tipo "a regra supera o classificador" estaria comparando uma tarefa sem
nenhum caso difícil (a regra) contra uma tarefa 90% `NONE` (o classificador) — **não é uma
comparação justa entre os dois métodos**, é uma comparação entre duas distribuições de dados
diferentes. Vale reportar os dois separadamente, não como "regra vence ML".

## Decisão

**Arquitetura híbrida (regra para `Patient`, classificador de N-gramas para o resto), resolução de
dados por offset de caractere (nunca por texto), e `LogisticRegression` como único modelo de
produção — mesmo quando `LinearSVC` vence o grid de comparação.**

Evidência, não suposição:

1. A resolução por offset reduziu a perda de cobertura de 38–75% (v1, casamento de texto) para
   28,6% (v2) — medido nos mesmos 56 casos, com as 181 colisões de deduplicação verificadas uma a
   uma como não gerando rótulo conflitante.
2. `LinearSVC` vence `LogisticRegression` em macro-F1 (0,761 vs 0,691 em `val`, config `1-1`), mas
   não tem `predict_proba` nativo — calibrar uma probabilidade aproximada por fora
   (`CalibratedClassifierCV`) adicionaria uma camada de incerteza extra à coluna `confidence` das
   predições finais, sem necessidade: a diferença de F1 entre os dois modelos é pequena frente ao
   tamanho das classes raras (`REVEALS` tem 5 exemplos em `val`), e `LogisticRegression` já entrega
   probabilidade exata.
3. A régua de que o classificador acerta recall 1,0 mas precisão baixa nas classes raras é
   consistente entre as 4 configurações do grid (não é ruído de uma config específica) — reforça
   que é comportamento do `class_weight="balanced"` sob desbalanço real, não artefato de uma escolha
   isolada.

## Limitações conhecidas

- **`SUPPORTS` tem suporte zero em `val`** — qualquer conclusão sobre essa classe específica não é
  sustentada pelos dados atuais; precisaria de mais casos anotados ou uma reamostragem de split para
  ficar mensurável.
- **A comparação regra-vs-classificador não é direta** — a regra nunca vê um `Patient` negativo, o
  classificador vê ~90% `NONE`. Reportar os dois separadamente.
- **`polarity`/`certainty` na saída são herdados dos atributos das arestas do Projeto 1**, repassados
  por `mock/gerar.py` — não há predição própria desses campos nesta etapa, porque a Etapa 3
  (tipos/polaridade) ainda não publicou saída real.
- **Nenhum teste automatizado cruza a fronteira `mock/gerar.py` → `relacoes.py`** — o contrato de
  colunas entre os dois (`COLUNAS` do gerador vs. o que `load_entities`/`build_feature_pipeline`
  esperam) só foi validado manualmente, rodando o pipeline completo nos dados reais.
- **Relações reflexivas são sempre descartadas** — `resolver_positivos` recusa um par onde origem e
  destino resolvem para a mesma menção. Isso afeta só `REVISES` (`Diagnosis`→`Diagnosis`), que tem 1
  ocorrência em todo o corpus — negligível nos dados atuais, mas é uma limitação estrutural, não um
  caso tratado.
- **Os 2 casos-gabarito de João (`PMC4630775_01`, `PMC6083636_03`) ainda não foram anotados à mão** —
  `evaluate_against_gold` já está pronta para uso, mas sem gabarito de relações ainda não há como
  validar as predições desta etapa contra anotação humana independente do próprio Projeto 1.
