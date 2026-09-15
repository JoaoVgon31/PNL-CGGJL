# 05 — Remoção de stop-words: decisão e experimento

> Entregável da [issue #5](https://github.com/caiomelloni/PNL-CGGJL/issues/5) — Projeto 1 (MC896, 2026).
> Estratégia obrigatória: remoção de stop-words. Código em [`src/projeto-1/stopwords/`](../../src/projeto-1/stopwords/).

## Contexto

Listas de stop-words foram desenhadas para recuperação de informação, onde uma palavra funcional
é ruído. A hipótese desta issue é que, em extração de entidades e relações de texto clínico, essa
suposição pode ser falsa: negação (`no`, `without`), modificadores de certeza e preposições que
disparam relações (`of`, `with`) carregam significado que uma lista genérica não distingue de
artigos e pronomes. Este documento não assume essa hipótese — mede.

## O pipeline e as 4 condições

`src/projeto-1/stopwords/` extrai as 11 entidades e 12 relações do contrato comum (docs
[01](01-dados-a-extrair.md)/[02](02-esquema-grafo.md)) via regex/léxico, e roda o mesmo conjunto de
extratores em 4 condições, variando só onde a remoção de stop-words entra:

| Condição | Onde a remoção age | Proteção aplicada? |
|---|---|---|
| `BASELINE` | nunca | — |
| `NAIVE_UNPROTECTED` | no `case_text`, antes da extração | não |
| `GUARDED_GLOBAL` | no `case_text`, antes da extração | sim |
| `GUARDED_LABEL` | só no `label` final, depois da extração | sim |

A remoção nunca deleta texto — substitui a palavra por espaços do mesmo tamanho, preservando
`char_start`/`char_end` para auditoria. A lista de proteção cobre só palavras isoladas de negação e
certeza (`no`, `not`, `without`, `never`, `denies`, `suggesting`, `consistent`, ...) — **não**
inclui `of`/`with`/`to`/`between`, para que o experimento meça a quebra real de entidades
multi-palavra e relações em vez de blindar o resultado por decisão de projeto.

Cada condição não-baseline roda com 3 listas: `nltk_stopwords` (198 palavras, do repositório
`nltk/nltk_data`), `spacy_stopwords` (326 palavras, de `explosion/spaCy`) e `custom_clinical`
(`nltk ∪ spacy − proteção`, 397 palavras). As 4 listas estão versionadas em
[`src/projeto-1/stopwords/lexicon/data/`](../../src/projeto-1/stopwords/lexicon/data/).

## Resultado agregado — 56 casos, 560 execuções

| Condição | Lista | Nós perdidos | Nós ganhos | `polarity_changed` | Arestas perdidas | Arestas ganhas | Pior caso | Flips no pior caso |
|---|---|---:|---:|---:|---:|---:|---|---:|
| `GUARDED_GLOBAL` | `custom_clinical` | 641 | 389 | 0 | 664 | 463 | `PMC5137649_01` | 0 |
| `GUARDED_GLOBAL` | `nltk_stopwords` | 638 | 387 | 0 | 662 | 462 | `PMC5137649_01` | 0 |
| `GUARDED_GLOBAL` | `spacy_stopwords` | 640 | 388 | 0 | 663 | 462 | `PMC5137649_01` | 0 |
| `GUARDED_LABEL` | `custom_clinical` | 494 | 492 | 0 | 539 | 537 | `PMC5137649_01` | 0 |
| `GUARDED_LABEL` | `nltk_stopwords` | 486 | 485 | 0 | 536 | 536 | `PMC5137649_01` | 0 |
| `GUARDED_LABEL` | `spacy_stopwords` | 492 | 490 | 0 | 538 | 536 | `PMC5137649_01` | 0 |
| `NAIVE_UNPROTECTED` | `custom_clinical` | 641 | 389 | 0 | 664 | 463 | `PMC5137649_01` | 0 |
| `NAIVE_UNPROTECTED` | `nltk_stopwords` | 649 | 398 | **14** | 672 | 472 | `PMC12832199_01` | 3 |
| `NAIVE_UNPROTECTED` | `spacy_stopwords` | 651 | 399 | **21** | 675 | 474 | `PMC12832199_01` | 3 |

(gerado por `python3 src/projeto-1/stopwords/run_experiment.py`; arquivo completo em
[`experiment_output/summary.csv`](../../src/projeto-1/stopwords/experiment_output/summary.csv).)

**`NAIVE_UNPROTECTED` — o erro cru.** Rodar a lista pronta (NLTK ou spaCy) direto sobre o texto,
sem proteção, inverte polaridade de verdade: 14 nós com `polarity` trocada com NLTK, 21 com spaCy —
mais, porque a lista do spaCy contém `without` e `never`, que a do NLTK não tem (só `no`/`not`).
Essa é a única diferença de risco entre as duas listas públicas, e ela é mensurável, não hipotética.
`NAIVE_UNPROTECTED×custom_clinical` bate **exatamente** com `GUARDED_GLOBAL×custom_clinical`
(641/389/0/664/463 nos dois) — checagem cruzada esperada, já que `custom_clinical` já nasce sem os
termos de proteção, então subtraí-los de novo não muda nada.

**`GUARDED_GLOBAL` — proteger negação não basta.** `polarity_changed=0` nas 3 listas confirma que
proteger `no`/`not`/`without`/`never` evita a inversão de sentido. Mas `nodes_lost`/`edges_lost`
continuam enormes (638–641 nós, 662–664 arestas perdidos em 56 casos, nas 3 listas) — porque `of`/`with`/`to`
ficam fora da proteção, e frases como `history of X` dependem de `of` para o gatilho da entidade
`History` funcionar. Mascarar `of` antes da extração quebra a entidade inteira, não só o rótulo.

**`GUARDED_LABEL` — os números agregados enganam.** `polarity_changed=0` de novo, e os números de
`nodes_lost`/`edges_lost` (486–539) parecem quase tão ruins quanto `GUARDED_GLOBAL` à primeira
vista. Não são: o método de comparação casa nós por `(tipo, label)` exato, e `GUARDED_LABEL` muda o
`label` de propósito (é a limpeza cosmética que a condição existe para fazer) — então qualquer
`label` encurtado já conta como "nó perdido + nó ganho" no diff, mesmo quando a entidade e a aresta
continuam intactas. Verificado caso a caso (ver próxima seção): sob `GUARDED_LABEL` com
`nltk_stopwords`, **0 de 56 casos** têm contagem de arestas diferente do baseline, e só **1 de 56**
tem contagem de nós diferente — e esse único caso é uma fusão benéfica, não uma perda.

## O caso mais interessante — PMC12832199_01

Duas inversões de sentido no mesmo caso, sob `NAIVE_UNPROTECTED × spaCy`:

**1. Um achado de exame vira o oposto do que o laboratório mostrou.**

> *"Laboratory data showed no progression of anemia and improvement in inflammatory markers."*

| condição | `label` | `polarity` |
|---|---|---|
| `BASELINE` | `no progression of anemia and improvement in inflammatory markers` | `absent` |
| `NAIVE_UNPROTECTED` × spaCy | `progression anemia improvement inflammatory markers` | **`present`** |

`no` e `of`/`and`/`in` são mascarados antes da extração — a regra de negação nunca vê o `no`, então
o `Finding` que deveria dizer "a anemia **não** progrediu" vira "a anemia progrediu": o grafo passa
a afirmar exatamente o oposto do que o texto diz.

**2. Um desfecho sem recorrência vira recorrência confirmada.**

> *"Only the elevated colon and its mesentery were seen protruding through the abdominal wall as the stoma, and no recurrence of the parastomal hernia was identified."*

| condição | `label` | `polarity` |
|---|---|---|
| `BASELINE` | `recurrence` | `absent` |
| `NAIVE_UNPROTECTED` × spaCy | `recurrence` | **`present`** |

Esse é o exemplo com a consequência clínica mais séria do experimento: o nó `Outcome` passa de
"sem recorrência da hérnia" para "recorrência", a leitura contrária da real.

**3. Efeito colateral no mesmo caso: 8 nós `History` inteiros desaparecem.** Sob `GUARDED_GLOBAL`
(qualquer lista) ou `NAIVE_UNPROTECTED`, o gatilho `history of` do extrator de `History` deixa de
casar assim que `of` é mascarado — as 8 menções de antecedente do caso (doença de Buerger,
amputações, insuficiência adrenal, cirurgias abdominais...) e as 8 arestas `HAS_HISTORY`
correspondentes somem por completo, não só mudam de rótulo. As tabelas completas (antes/depois,
nós e arestas) estão em
[`experiment_output/highlight_case/`](../../src/projeto-1/stopwords/experiment_output/highlight_case/).

## Decisão

**Aplicar remoção de stop-words, mas só como limpeza do `label` depois da extração
(`GUARDED_LABEL`), nunca antes ou durante a detecção de entidade/relação — e com a lista do NLTK,
não a customizada.**

Evidência, não suposição:

1. `GUARDED_LABEL` nunca inverteu `polarity` — 0 de 56 casos, nas 3 listas, confirmado tanto no
   agregado quanto por um teste de regressão dedicado
   (`tests/experiment/test_diff.py::test_guarded_label_never_flips_polarity_in_diff`) que compara o
   atributo diretamente no grafo, não só via o método de diff por `(tipo, label)`.
2. Verificado caso a caso nos 56 casos: `GUARDED_LABEL` com `nltk_stopwords` produz **arestas
   idênticas, byte a byte, em 56 de 56 casos**, e contagem de nós idêntica em 55 de 56. O único caso
   com contagem diferente (`PMC5804616_01`, 29→28 nós) é uma fusão *desejável*: o baseline já tinha
   dois `ExamResult` espúrios (`"With an FiO2"` e `"with an FiO2"`, distintos só pela maiúscula
   inicial de começo de frase) que a limpeza de stop-words unifica em um só `FiO2` — corrige um
   defeito do próprio baseline, não perde informação clínica distinta.
3. **A lista customizada não é a mais segura aqui.** Testada nos mesmos 56 casos, `custom_clinical`
   causa 2 de 56 fusões de nó, uma delas prejudicial: em `PMC10106591_01`, o `Diagnosis` `"CAS was
   made"` (uma confirmação) colapsa para o mesmo `label` de um `Diagnosis` `"CAS"` anterior e não
   relacionado, porque `custom_clinical` herda `made` da lista do spaCy — o NLTK não tem essa
   palavra. Resultado: a distinção entre uma suspeita anterior e a confirmação do diagnóstico se
   perde silenciosamente. Trocar para `nltk_stopwords` elimina essa colisão sem custo — daí a lista
   final escolhida ser o NLTK, não a nossa própria lista mais abrangente.
4. `GUARDED_GLOBAL` e `NAIVE_UNPROTECTED`, em qualquer lista, causam perda estrutural real e
   substancial (638–651 nós, 662–675 arestas, em 56 casos) por mascarar preposições de gatilho antes
   da extração — não são candidatos, independente de proteger ou não a negação.

As tabelas finais em [`src/projeto-1/stopwords/output/`](../../src/projeto-1/stopwords/output/) (56
casos) foram geradas com essa configuração:
rodando a partir de `src/projeto-1`:
`python3 -m stopwords --cases ../../sample/cases.csv --all-cases --condition GUARDED_LABEL --wordlist nltk_stopwords`.

## Listas versionadas

Em [`src/projeto-1/stopwords/lexicon/data/`](../../src/projeto-1/stopwords/lexicon/data/):

- `nltk_stopwords.txt` — cópia exata de `stopwords/english` do repositório `nltk/nltk_data`.
- `spacy_stopwords.txt` — cópia exata de `STOP_WORDS` em `spacy/lang/en/stop_words.py`, do
  repositório `explosion/spaCy`.
- `protection_list.txt` — nossa: negação e certeza, uma palavra por linha.
- `custom_clinical.txt` — nossa: `(nltk ∪ spacy) − proteção`, gerada e congelada como arquivo
  estático (não recalculada em runtime).

## Limitações conhecidas

- `core/graph.py` deduplica nós por `(tipo, label)` exato. Uma segunda menção da mesma entidade com
  um atributo divergente (ex.: `polarity` diferente) não sobrescreve o primeiro nó — só preenche
  campos vazios. Isso é ortogonal à remoção de stop-words, mas afeta a leitura de qualquer tabela
  gerada por este pipeline.
- A lista de proteção cobre só palavras isoladas (o mecanismo de mascaramento opera por token, não
  por frase). Gatilhos compostos que combinam uma palavra protegida com uma preposição desprotegida
  (`free of`, `ruled out`, `suggestive of`, `consistent with`) ficam parcialmente vulneráveis sob
  `GUARDED_GLOBAL`/`NAIVE_UNPROTECTED` — a palavra de conteúdo sobrevive, mas `of`/`out`/`with` pode
  ser mascarada. Não afeta a condição escolhida (`GUARDED_LABEL`), que não mascara o texto de
  extração.
- `polarity_changed` no resumo agregado é um **piso, não um total**: só conta uma inversão quando o
  `label` do nó sobrevive intacto o suficiente para casar entre o baseline e a variante mascarada.
  O próprio caso em destaque prova isso — a inversão do `Finding` de anemia é real e discutida acima,
  mas não está entre os 14/21 contados, porque o `label` também mudou sob mascaramento e o nó passou
  a contar como `nodes_lost`/`nodes_gained` em vez de `polarity_changed`. Isso reforça, não enfraquece,
  o argumento contra `NAIVE_UNPROTECTED`: o número real de inversões é maior que o reportado.
