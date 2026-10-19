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
(62+181)/842 ≈ **28,9%** — bem menor que os 38–75% da v1, e sem nenhum casamento por texto residual.

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

**A regra do paciente nunca vê um exemplo negativo.** De 430 pares envolvendo `Patient` nos dados
gerados, 430 são positivos e 0 são `NONE` — o gerador nunca cria um candidato negativo em que
`Patient` participa, porque a regra resolve esses pares por tipo, não por classificação. Uma
conclusão de relatório do tipo "a regra supera o classificador" estaria comparando uma tarefa sem
nenhum caso difícil (a regra) contra uma tarefa 90% `NONE` (o classificador) — **não é uma
comparação justa entre os dois métodos**, é uma comparação entre duas distribuições de dados
diferentes. Vale reportar os dois separadamente, não como "regra vence ML".

## Validação contra gabarito manual independente

Os 2 casos reservados do João (`PMC4630775_01`, `PMC6083636_03`) foram anotados à mão (texto lido do
zero, sem copiar as relações do Projeto 1 sem revisar) e integrados à infraestrutura oficial de
gabarito do time (`project2/data/gold/cases/`, mergeada em `main` pela Etapa 5 — `casos.txt`,
`<case_id>-entities.csv` com candidatos auto-extraídos e offset, `<case_id>-relations.csv` por
anotador, consolidados por `gold_manager.py` em `gold_relacoes.csv`/`manifest.json`). A migração do
nosso esquema de IDs próprio para os `ent_id` oficiais (`t1`, `t2`...) passou pela validação formal
do time sem nenhum erro (`python3 -m project2.src.montagem.data.gold_manager --consolidate`: 8 casos
validados, nossas 27 relações somadas às 86 dos demais = 113 no total).

Avaliado com `python3 -m project2.src.relacoes.avaliar_gabarito`:

```
total_predicted=37  total_gold=27  aligned_pairs=21
relation_precision=0,568  relation_recall=0,778  relation_f1=0,656
```

Nos 21 pares em que modelo e gabarito concordam que existe uma relação, **100% dos rótulos batem**
(`HAS_FINDING`, `HAS_RESULT`, `HAS_SYMPTOM`, `LOCATED_IN`, `UNDERWENT_EXAM` — precision/recall 1,00
em todas). O erro inteiro está em *quais* pares têm relação, não em qual relação é:

- **6 relações do gabarito não foram previstas** (recall perdido): todos os 6 `LOCATED_IN` de
  resultado→olho em `PMC6083636_03` (acuidade, Ishihara e Farnsworth-Munsell) — o modelo não
  generalizou essa relação quando a origem é um valor numérico de resultado (`ExamResult`), só
  quando a origem é um sintoma.
- **16 pares sem relação no gabarito foram previstos como se tivessem** (precisão baixa): o padrão
  mais visível é `Exam/Finding→Finding` classificado como `REVEALS` (8 pares, ex. "exame revela
  nistagmo"), `Patient→AnatomicalSite` como `LOCATED_IN` sem sentido clínico (3 pares), e
  `Symptom→AnatomicalSite` generalizado para todo sítio anatômico do caso em vez de só o correto
  (5 pares em `PMC4630775_01`, ex. "desquamation" ligado a "skin"/"thumb"/"forearm" além de "palm").

Essa é a mesma assinatura de erro já vista nos dados mock (seção anterior): recall alto, precisão
baixa nas classes raras, efeito do `class_weight="balanced"` sob desbalanço — agora confirmada contra
anotação humana independente do Projeto 1, não só contra dados derivados dele.

**Nota sobre a migração:** o campo `type` do `entities.csv` oficial herda o mesmo bug de casamento de
texto que motivou nosso `mock/gerar.py` (seção "O problema da v1..."): sítios anatômicos mencionados
dentro do blob de sintoma do Projeto 1 saem rotulados `Symptom`. `avaliar_gabarito.py` corrige isso
só para os `ent_id` dos nossos 2 casos (`TYPE_OVERRIDE`, não edita o arquivo compartilhado) e descarta
candidatos sem tipo (ruído do chunker automático — frases das perguntas no fim do texto, nunca
presentes no treino real, que só usa menções já tipadas pela Etapa 2).

## Decisão

**Arquitetura híbrida (regra para `Patient`, classificador de N-gramas para o resto), resolução de
dados por offset de caractere (nunca por texto), e `LogisticRegression` como único modelo de
produção — mesmo quando `LinearSVC` vence o grid de comparação.**

Evidência, não suposição:

1. A resolução por offset reduziu a perda de cobertura de 38–75% (v1, casamento de texto) para
   28,9% (v2) — medido nos mesmos 56 casos, com as 181 colisões de deduplicação verificadas uma a
   uma como não gerando rótulo conflitante.
2. `LinearSVC` vence `LogisticRegression` em macro-F1 por uma margem real, não desprezível (0,761 vs
   0,691 em `val`, config `1-1`) — mas isso não decide a escolha do modelo de produção, porque
   `confidence` é uma coluna exigida pela issue para toda predição (`project2/data/relacoes.csv`
   "relações do caso com confiança"), não um subproduto específico de um modelo. `LogisticRegression`
   fornece essa confiança nativamente via `predict_proba`, sem custo extra, inclusive para a classe
   mais rara do treino (`SUPPORTS`, 3 exemplos). `LinearSVC` não tem `predict_proba` nativo; o caminho
   padrão para obter uma confiança a partir dele (`CalibratedClassifierCV`, Platt scaling) **falha de
   forma reproduzível nesses dados**: `cv=5` exige ao menos 5 exemplos por classe, e `SUPPORTS` tem 3
   no treino —
   ```
   ValueError: Requesting 5-fold cross-validation but provided less than 5 examples for at least one class.
   ```
   Contornar isso (reduzir `cv`, abandonar estratificação, agrupar classes) adicionaria engenharia não
   padrão exatamente na classe que o relatório já marca como frágil (suporte zero em `val`, ponto 3
   abaixo). A decisão não é "confiança exata é melhor que aproximada" — nenhuma das duas foi validada
   por calibração (reliability curve/Brier score, não medido para nenhum dos dois modelos). É que
   `LogisticRegression` produz o campo exigido para toda classe mecanicamente, e `LinearSVC` não
   produz para a mais rara sem um remendo não testado.
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
- **A avaliação contra gabarito (seção acima) cobre só 2 casos, 27 relações** — amostra pequena
  demais para generalizar a magnitude exata de precisão/recall; serve como confirmação qualitativa
  do padrão de erro (recall alto, precisão baixa), não como medida definitiva.
- **`avaliar_gabarito.py` ainda não generaliza para um novo caso-gabarito sem ajuste manual** — desde
  a migração para `project2/data/gold/cases/<case_id>-entities.csv` oficial, os offsets já vêm
  prontos (não precisa mais localizar texto na mão), mas os dicionários `PATIENT_ENT_ID` e
  `TYPE_OVERRIDE` (que corrigem o bug de tipo herdado do `weak_supervision.py`, ver seção de
  validação acima) ainda são por caso — um novo caso-gabarito exigiria adicionar suas entradas.
- **A coluna `confidence` ainda não tem consumidor** — `project2/src/montagem/assembly/pipeline.py`
  (Etapa 5) não filtra nem usa esse valor hoje. A coluna é gerada porque a issue exige (anotação de
  incerteza por aresta, mesmo papel que `certainty` já cumpre nas arestas do Projeto 1), não porque
  algo no pipeline atual consome o número — fica disponível para quando a montagem do grafo (ou um
  revisor humano) quiser usá-lo.
