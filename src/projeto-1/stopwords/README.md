# Stop-words

Pipeline `case_text` → grafo de conhecimento (issue #5), e o experimento que decide se, onde e com
qual lista aplicar remoção de stop-words. Ver a decisão completa, com os números do experimento, em
[docs/projeto-1/05-stopwords.md](../../../docs/projeto-1/05-stopwords.md). Este README é sobre como
rodar o código; aquele documento é sobre por que a decisão foi essa.

## O que foi feito

O pipeline lê o `case_text` de um caso clínico e extrai, por regex e léxico, as 11 entidades e 12
relações do contrato comum do projeto (docs
[01](../../../docs/projeto-1/01-dados-a-extrair.md)/[02](../../../docs/projeto-1/02-esquema-grafo.md)):
sintomas, antecedentes, achados, exames, resultados, diagnósticos, tratamentos, medicamentos,
sítios anatômicos e desfechos, ligados ao paciente e entre si. A saída são duas tabelas — nós e
arestas — no formato comum às issues #3–#6.

Sobre esse pipeline, a issue pedia que a estratégia de remoção de stop-words fosse implementada e
**medida**, não assumida. O mesmo extrator roda em 4 condições, variando só onde (ou se) a remoção
age: nunca (`BASELINE`), no texto bruto sem proteger negação (`NAIVE_UNPROTECTED`), no texto bruto
protegendo negação (`GUARDED_GLOBAL`), ou só no `label` do nó já extraído (`GUARDED_LABEL`). Rodamos
as 4 condições × 3 listas (NLTK, spaCy, uma customizada) sobre os 56 casos reais da amostra e
comparamos as tabelas geradas, não os tokens removidos.

**Como isso ajuda a parsear o grafo:** por si só, a remoção de stop-words não ajuda a extrair nada —
os extratores já funcionam sobre o texto completo. O que a remoção pode ajudar é a *qualidade dos
rótulos* depois que a entidade já foi identificada: `"a laparoscopic distal pancreatectomy"` e
`"laparoscopic distal pancreatectomy"` são a mesma cirurgia, mas o `GraphBuilder` deduplica nós por
`(tipo, label)` **exato** — sem normalizar artigos/preposições, duas menções da mesma entidade com
texto ligeiramente diferente viram dois nós em vez de um. Aplicada só na limpeza final do `label`
(`GUARDED_LABEL`), a remoção aumenta a chance de duas menções colapsarem no nó certo, sem tocar a
detecção de negação, certeza ou relação. É esse ganho — modesto, e não uma reformulação da extração
— que a decisão final persegue.

## Como usar

A partir da raiz do repositório, entrando em `src/projeto-1` (os módulos são importados como
`stopwords.*`, então os comandos precisam rodar daqui):

```bash
cd src/projeto-1
```

**Processar um caso e ver as tabelas.** Gera `<case_id>-nodes.csv` e `<case_id>-edges.csv` no
diretório de saída (padrão: `stopwords/output/`):

```bash
python3 -m stopwords --cases ../../sample/cases.csv --case-id PMC5137649_01
```

**Processar todos os casos do CSV de uma vez** (usado para gerar o conteúdo hoje versionado em
`output/`):

```bash
python3 -m stopwords --cases ../../sample/cases.csv --all-cases --output stopwords/output
```

**Escolher a condição de remoção de stop-words** (por padrão é `BASELINE`, sem remoção nenhuma):

```bash
python3 -m stopwords --cases ../../sample/cases.csv --case-id PMC5137649_01 \
  --condition GUARDED_LABEL --wordlist nltk_stopwords
```

`--condition` aceita `BASELINE`, `NAIVE_UNPROTECTED`, `GUARDED_GLOBAL`, `GUARDED_LABEL`.
`--wordlist` aceita `nltk_stopwords`, `spacy_stopwords`, `custom_clinical` — obrigatório para
qualquer condição além de `BASELINE`; se faltar, o programa termina com uma mensagem de erro (não
um traceback) e código de saída 1. Um `--case-id` inexistente no CSV também termina de forma limpa,
com o mesmo tratamento.

**Rodar o experimento completo** (as 4 condições × 3 listas sobre todos os casos do CSV apontado
dentro do script, e gravar o resumo agregado). É o que gerou
`experiment_output/summary.csv`/`summary.json`:

```bash
python3 stopwords/run_experiment.py
```

**Rodar os testes:**

```bash
python3 -m unittest discover -s stopwords/tests -t . -p "test_*.py"
```

## Estrutura

- `core/`: modelos (`Node`, `Edge`) e `GraphBuilder` (dedup, ids);
- `extractors/`: um módulo por entidade + `relations.py` para as 12 arestas;
- `lexicon/`: as 4 listas versionadas (`data/`) + `masking.py`/`label_cleaning.py`/`loader.py`;
- `exporters/`: exportação CSV;
- `experiment/`: as 4 condições, o diff por conteúdo, o runner e o relatório agregado;
- `tests/`: `unittest`, espelhando a estrutura acima;
- `output/`: nodes/edges csv dos 56 casos da amostra, na configuração final decidida
  (`GUARDED_LABEL` + `nltk_stopwords`);
- `experiment_output/`: `summary.csv`/`.json` e as tabelas do caso mais dramático
  (`highlight_case/`).

## Onde essa estratégia falha

A remoção de stop-words não é neutra em texto clínico, e o experimento mede exatamente onde ela
quebra:

- **Mascarar o texto antes da extração inverte o sentido do grafo.** Sob `NAIVE_UNPROTECTED`, a
  lista de stop-words (NLTK ou spaCy) é aplicada sem proteger negação. Um achado como *"no
  progression of anemia"* (`polarity=absent`) perde o `no` antes de qualquer regra de negação rodar,
  e o nó final registra `polarity=present` — o oposto exato do texto original. Isso aconteceu em 14
  nós (lista do NLTK) e 21 nós (lista do spaCy) nos 56 casos reais — a lista do spaCy é mais
  arriscada porque também contém `without`/`never`, que a do NLTK não tem. Caso concreto em
  [`experiment_output/highlight_case/`](experiment_output/highlight_case/).
- **Proteger a negação não é suficiente.** Sob `GUARDED_GLOBAL`, `polarity` nunca inverte, mas
  `of`/`with`/`to`/`between` continuam fora da lista de proteção — e várias entidades dependem
  dessas preposições no próprio gatilho (`history of X`, `level of Y`). Mascará-las antes da
  extração faz a entidade inteira desaparecer, não só o rótulo: nos 56 casos, isso derrubou entre
  638 e 641 nós e entre 662 e 664 arestas, dependendo da lista.
- **A lista de proteção só cobre palavras isoladas.** Gatilhos compostos por uma palavra protegida
  e uma preposição desprotegida (`free of`, `ruled out`, `suggestive of`, `consistent with`) ficam
  parcialmente vulneráveis mesmo sob `GUARDED_GLOBAL` — a palavra de conteúdo sobrevive, mas a
  preposição pode ser mascarada e quebrar o casamento do gatilho.
- **Mesmo a variante "segura" (`GUARDED_LABEL`) pode fundir entidades diferentes por engano**, se a
  lista escolhida for agressiva demais. Testado com `custom_clinical` (nossa lista, mais ampla),
  `"CAS was made"` (uma confirmação de diagnóstico) colapsou para o mesmo rótulo de um `"CAS"`
  anterior e não relacionado (uma suspeita), porque essa lista herda `made` do spaCy — o NLTK não
  tem essa palavra. Foi por isso que a lista final escolhida é a do NLTK, e não a nossa própria
  lista, mais abrangente.
- **A métrica agregada `polarity_changed` é um piso, não um total.** Como nós são casados por
  `(tipo, label)` entre a execução com e sem remoção, uma inversão de sentido só é contada quando o
  `label` sobrevive intacto o bastante para continuar batendo com o baseline. Quando o mascaramento
  muda o `label` (o caso mais comum), a mesma inversão aparece como nó perdido/ganho, não como
  `polarity_changed` — os números de 14/21 citados acima estão subestimados, não superestimados.

Detalhes, números completos e a decisão final (aplicar remoção só via `GUARDED_LABEL`, com a lista
do NLTK) estão em [docs/projeto-1/05-stopwords.md](../../../docs/projeto-1/05-stopwords.md).
