# 03 — Parser caso → grafo com estratégia de tokenização

## 1. Objetivo

Esta implementação atende à issue #3. O programa recebe um `case_id`, encontra
o respectivo `case_text` no `cases.csv`, tokeniza o texto, executa uma extração
clínica simples e produz as duas tabelas do contrato do projeto:

| tabela | colunas |
|---|---|
| nós | `case_id`, `node_id`, `type`, `label`, `attributes` |
| arestas | `case_id`, `edge_id`, `source_id`, `target_id`, `relation`, `attributes` |

A estratégia estudada em profundidade é a **tokenização**. As demais etapas
usam regras e léxicos pequenos para tornar mensurável o efeito da troca do
tokenizador no grafo final.

As técnicas utilizadas são tokenização por regras, expressões regulares,
casamento de padrões e dicionários explícitos. O NLTK é usado somente para
executar o tokenizador clássico Treebank na comparação.

## 2. Visão geral do pipeline

```text
cases.csv + case_id
        │
        ▼
   ClinicalCase
        │
        ▼
    Tokenizer ───────────────┐
        │                    │
        ▼                    │
 list[Token]                 │ troca controlada entre
        │                    │ whitespace, Treebank e regex clínico
        ▼                    │
 regras e léxicos ◄──────────┘
        │
        ▼
   GraphBuilder
     │      │
     ▼      ▼
 nodes.csv edges.csv
```

A mesma função de extração recebe a saída de qualquer um dos três
tokenizadores. Portanto, quando a quantidade de `ExamResult` ou de arestas
`HAS_RESULT` muda, a diferença foi causada pela fronteira dos tokens, e não por
uma troca escondida nas regras de extração.

## 3. Organização dos arquivos

| arquivo | responsabilidade |
|---|---|
| `models.py` | `Token`, `ClinicalCase`, `Node`, `Edge` e validações |
| `tokenizers.py` | três tokenizadores e classificação das superfícies |
| `case_reader.py` | leitura e validação do `cases.csv` |
| `extraction.py` | regras simples de entidades, medições e relações |
| `graph.py` | IDs, deduplicação e validação do grafo |
| `pipeline.py` | orquestração do caso até o grafo |
| `evaluation.py` | casos difíceis e métricas sobre a amostra |
| `serialization.py` | escrita dos CSVs e JSONs |
| `mermaid_export.py` | grafo completo e recorte Mermaid para os slides |
| `main.py` | interface de linha de comando |
| `requirements.txt` | dependência comparativa do NLTK |

Os testes estão em `project1/src/tokenizacao/tests/`. As saídas reproduzidas para
o caso `PMC5137649_01` e para a amostra estão em `project1/src/tokenizacao/output/`.

## 4. O que é um token neste projeto

Um token não é apenas uma string. Ele possui cinco campos:

```python
Token(
    text="12,476.5",
    start=157,
    end=165,
    index=31,
    kind="NUMBER",
)
```

Os offsets adotam um intervalo semiaberto: `start` é incluído e `end` é
excluído. A propriedade fundamental é:

```python
case_text[token.start:token.end] == token.text
```

Essa propriedade é verificada depois de cada tokenização. Também são validadas
as seguintes invariantes:

1. índices começam em zero e são sequenciais;
2. tokens não se sobrepõem;
3. qualquer trecho ignorado entre dois tokens contém somente espaços;
4. nenhum caractere não branco desaparece silenciosamente.

Os offsets permitem recuperar a evidência original, mesmo quando o valor é
normalizado depois. Por exemplo, `12,476.5ng/ml` é guardado como `raw_text`,
enquanto o valor comparável passa a ser `Decimal("12476.5")` e a unidade passa
a ser `ng/mL`.

## 5. Abordagens comparadas

### 5.1 Baseline por espaços

O `WhitespaceTokenizer` usa a expressão `\S+`: cada sequência entre espaços é
um token. Ele preserva offsets, mas não entende pontuação nem elementos colados.

```text
12,476.5ng/ml → [12,476.5ng/ml]
6cm x 9cm     → [6cm, x, 9cm]
(Fig 1)       → [(Fig, 1)]
```

Esse baseline materializa o comportamento equivalente a usar `split()` e
serve como controle experimental. Ele não é a abordagem escolhida.

### 5.2 Treebank do NLTK

O `TreebankTokenizer` adapta `nltk.tokenize.TreebankWordTokenizer`. Trata-se de
um tokenizador clássico, baseado em regras criadas para a convenção do Penn
Treebank. Foi usado `span_tokenize()`, não `tokenize()`, porque o primeiro
fornece os offsets no texto original.

Essa classe não exige download de corpus ou modelo. A dependência NLTK contém
as regras do tokenizador. O Treebank lida bem com pontuação geral, mas não foi
projetado para unidades clínicas coladas a números.

### 5.3 Regex clínico

O `ClinicalRegexTokenizer` é a abordagem escolhida. Ele aplica uma expressão
regular mestra com grupos nomeados. Cada grupo corresponde a um tipo de token:

| grupo | exemplo |
|---|---|
| `FIGURE_REF` | `(Fig 1)`, `(Figs 3-5)` |
| `NUM_HYPHEN_WORD` | `44-year-old`, `3-day` |
| `NUMBER_RANGE` | `10-140`, `0-0.04`, `19-9` |
| `NUMBER` | `12,476.5`, `0.016`, `6` |
| `UNIT` | `ng/ml`, `U/L`, `cm`, `iu/ml` |
| `OPERATOR` | `<`, `>=` |
| `WORD` | `patient`, `EUS-FNA`, `body/tail` |
| `PUNCTUATION` | `.`, `,`, `(` |

### 5.4 Por que a ordem das regras importa

A expressão regular testa as alternativas da esquerda para a direita. As
construções mais específicas precisam aparecer antes das mais gerais.

Por exemplo, se `NUMBER` aparecesse antes de `NUMBER_RANGE`, a superfície
`10-140` seria quebrada em `10`, `-` e `140`. Se `WORD` aparecesse antes de
`UNIT`, `ng/ml` seria classificado como uma palavra comum. Se a referência de
figura não viesse primeiro, `(Fig 1)` seria dividida em quatro tokens.

A sequência adotada é:

```text
FIGURE_REF
→ NUM_HYPHEN_WORD
→ NUMBER_RANGE
→ NUMBER
→ UNIT
→ OPERATOR
→ WORD
→ PUNCTUATION
```

## 6. Decisões para os casos difíceis

| texto original | saída escolhida | justificativa |
|---|---|---|
| `12,476.5ng/ml` | `12,476.5` + `ng/ml` | separa valor e unidade sem perder a vírgula de milhar |
| `6cm x 9cm` | `6` + `cm` + `x` + `9` + `cm` | permite reconstruir uma medida multidimensional |
| `6iu/ml` | `6` + `iu/ml` | a barra pertence à unidade |
| `EUS-FNA` | um `WORD` | o hífen faz parte da sigla composta |
| `contrast-enhanced` | um `WORD` | composto lexical, não intervalo numérico |
| `CA 19-9` | `CA` + `19-9` | o espaço é fronteira; o extrator posterior pode reconhecer a sequência |
| `(Fig 1)` | um `FIGURE_REF` | marca ruído editorial sem apagá-lo antes da auditoria |
| `10-140 U/L` | `10-140` + `U/L` | mantém a faixa distinta da unidade |
| `body/tail` | um `WORD` | a barra une duas regiões qualificadoras |

`19-9` e `10-140` têm a mesma forma gráfica. O tokenizador classifica ambos
como `NUMBER_RANGE`; decidir se representam nome de exame ou faixa de
referência depende do contexto e pertence à extração, não à tokenização.

Uma referência de figura é mantida na lista com o tipo `FIGURE_REF`. Os
extratores não a usam como parte de entidade. Isso é preferível a apagá-la na
tokenização, pois o offset e a superfície continuam auditáveis.

## 7. Como a tokenização alimenta o grafo

### 7.1 Entidades lexicais

O extrator procura sequências de tokens em léxicos pequenos de sintomas,
antecedentes, exames, achados, diagnósticos, medicamentos, tratamentos, sítios
anatômicos e desfechos. Alguns tipos exigem um contexto:

- `History` exige a palavra `history` na sentença;
- `Diagnosis` exige gatilho como `diagnosis of`, `consistent with` ou
  `suggesting`;
- `Medication` e `Treatment` exigem gatilho como `treated with`, `underwent`,
  `dose of` ou `administered`.

O nó `Patient` é sempre criado e ancora o grafo. Idade e gênero são buscados no
texto por uma regra explícita, com os valores do CSV como fallback.

### 7.2 Valor e unidade

A extração quantitativa percorre tokens adjacentes:

```text
NUMBER seguido de UNIT
```

Assim, a decisão do tokenizador tem efeito direto. Com o regex clínico:

```text
12,476.5ng/ml
├── NUMBER  12,476.5
└── UNIT    ng/ml
```

Com o baseline por espaços há apenas um token `RAW`, portanto a regra não
encontra o resultado.

Quando a unidade é `cm` ou `mm`, a medição é tratada como tamanho de um
`Finding`. O padrão continua enquanto encontra `x NUMBER UNIT`, permitindo
preservar `9.5cm x 4.5cm x 2.0cm` por inteiro. Para unidades laboratoriais, é
criado um `ExamResult` ligado ao exame mais próximo da mesma sentença por
`HAS_RESULT`.

As unidades são normalizadas por uma tabela explícita, por exemplo:

```text
ng/ml → ng/mL
iu/ml → IU/mL
u/l   → U/L
/ul   → /µL
```

### 7.3 Nós, arestas e evidência

O `GraphBuilder` gera IDs conforme o contrato: `P1`, `S1`, `E1`, `R1` etc., e
arestas `e1`, `e2`, ... Tipos e relações são validados contra listas fechadas.

Toda aresta armazena:

- `evidence_text`;
- `trigger`;
- `certainty` (`asserted` ou `hedged`);
- `char_start`;
- `char_end`.

Também vale a invariante:

```python
case_text[char_start:char_end] == evidence_text
```

## 8. Avaliação

### 8.1 Teste controlado dos casos difíceis

Foram usados os nove fenômenos da tabela da seção 6. Um caso é considerado
correto somente quando a lista de superfícies é exatamente a esperada e todos
os offsets recuperam o texto original.

| tokenizador | casos corretos |
|---|---:|
| espaços | 5/9 |
| Treebank | 5/9 |
| regex clínico | **9/9** |

Os dois tokenizadores gerais falham principalmente em valores e unidades
colados e no agrupamento da referência de figura. O regex clínico passa nos
nove casos porque possui regras explícitas para esses fenômenos.

### 8.2 Impacto sobre os 56 casos da amostra

A avaliação percorreu as 56 linhas reais do `cases.csv`. Os três tokenizadores
foram usados com o mesmo extrator.

| tokenizador | tokens | nós | arestas | `ExamResult` | `HAS_RESULT` |
|---|---:|---:|---:|---:|---:|
| espaços | 27.983 | 297 | 288 | 0 | 0 |
| Treebank | 31.356 | 629 | 696 | 235 | 235 |
| regex clínico | **32.835** | **755** | **929** | **330** | **330** |

O regex clínico produziu 95 resultados quantitativos a mais que o Treebank
(`330 - 235`) e 330 a mais que o baseline por espaços. O motivo principal é a
separação de superfícies como `12,476.5ng/ml`, `6iu/ml` e outras combinações
sem espaço.

Essas contagens representam **rendimento estrutural**, não precisão clínica.
Mais nós não significam automaticamente um grafo melhor: um resultado pode ser
um falso positivo ou estar ligado ao exame errado. Sem uma anotação humana de
referência não é correto chamar esses números de precisão, revocação ou F1.

O relatório reproduzível completo está em
`project1/src/tokenizacao/output/sample-comparison.json`.

### 8.3 Caso concreto `PMC5137649_01`

Nesse caso, o regex clínico separa:

```text
12,476.5ng/ml → 12,476.5 | ng/ml
6iu/ml        → 6 | iu/ml
```

Isso permite criar dois nós `ExamResult`, preservando os textos crus:

```text
value=12476.5; unit=ng/mL; raw_text=12,476.5ng/ml
value=6; unit=IU/mL; raw_text=6iu/ml
```

Ele também transforma:

```text
9.5cm x 4.5cm x 2.0cm
```

em uma dimensão única normalizada como:

```text
9.5 cm x 4.5 cm x 2.0 cm
```

As referências `(Fig 1)`, `(Fig 2)` e `(Figs 3-5)` são marcadas como ruído e
não entram nos rótulos clínicos.

## 9. Como executar

### 9.1 Criar ambiente e instalar a comparação NLTK

Na raiz do repositório:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r project1/src/tokenizacao/requirements.txt
```

### 9.2 Gerar o grafo de um caso

```bash
python3 project1/src/tokenizacao/main.py \
  --cases project1/sample/cases.csv \
  --case-id PMC5137649_01 \
  --tokenizer clinical_regex \
  --output project1/src/tokenizacao/output
```

### 9.3 Comparar os três tokenizadores no caso

```bash
python3 project1/src/tokenizacao/main.py \
  --cases project1/sample/cases.csv \
  --case-id PMC5137649_01 \
  --compare \
  --output project1/src/tokenizacao/output
```

### 9.4 Avaliar toda a amostra

```bash
python3 project1/src/tokenizacao/main.py \
  --cases project1/sample/cases.csv \
  --evaluate-sample \
  --output project1/src/tokenizacao/output
```

### 9.5 Executar os testes

```bash
python3 -m unittest discover -s project1/src/tokenizacao/tests -v
```

## 10. Testes automatizados

A suíte contém 14 testes e verifica:

- os nove casos difíceis da issue;
- tipos especiais de token;
- preservação dos offsets;
- ausência de perda silenciosa de caracteres Unicode;
- comportamento deliberadamente ruim do baseline;
- execução do Treebank sem baixar corpus;
- geração dos tipos de nó e relações esperados;
- extração de valor e unidade colados;
- diferença mensurável no grafo ao trocar o tokenizador;
- recuperação da evidência de todas as arestas pelos offsets;
- exclusão de referência de figura dos diagnósticos;
- leitura do CSV e exportação das três tabelas.

## 11. Limitações conhecidas

### 11.1 O vocabulário de unidades é finito

Uma unidade não listada será classificada como palavra ou pontuação. A solução
é ampliar `UNIT_VARIANTS` a partir dos erros observados, sempre adicionando um
teste de regressão.

### 11.2 Ambiguidade depende de contexto

`19-9` pode fazer parte de `CA 19-9`, enquanto `10-140` pode ser uma faixa. A
forma sozinha não resolve a semântica. O extrator atual usa contexto simples e
pode errar.

### 11.3 Léxicos clínicos têm cobertura pequena

Os dicionários em `extraction.py` são deliberadamente rudimentares. Eles não
cobrem todas as doenças, exames e medicamentos do MultiCaRe. Isso afeta a
quantidade e o tipo dos nós, mas não invalida a comparação controlada entre os
tokenizadores.

### 11.4 Relações usam sentença e proximidade

O exame mais próximo na mesma sentença recebe o resultado. Uma sentença com
vários exames e vários valores pode gerar uma associação incorreta. Resolver
isso exigiria regras de escopo mais sofisticadas ou análise sintática.

### 11.5 Não há correferência

Menções como `the cyst`, `the lesion` e `it` não são resolvidas como a mesma
entidade por raciocínio discursivo. A deduplicação usa rótulo e alguns atributos
explícitos.

### 11.6 Quantidade não é qualidade

As métricas atuais mostram o impacto mecânico no grafo. Para medir qualidade
clínica seria necessário anotar manualmente uma amostra e comparar entidades,
atributos e relações com esse gabarito.

## 12. Resumo para apresentação

Uma explicação curta pode seguir esta ordem:

1. `split()` falha quando valor e unidade estão colados;
2. cada token precisa carregar offsets para permitir auditoria;
3. o Treebank é um bom baseline geral, mas não conhece convenções clínicas;
4. o regex clínico protege primeiro as construções mais específicas;
5. no teste controlado, o resultado mudou de 5/9 para 9/9;
6. na amostra, `ExamResult` mudou de 235 para 330 em relação ao Treebank;
7. esse aumento é rendimento, não precisão, e as limitações foram registradas.

O exemplo visual mais direto é:

```text
Treebank/geral:  [12,476.5ng/ml]
Regex clínico:   [12,476.5] [ng/ml]
                              │
                              └── cria value + unit e permite HAS_RESULT
```

Essa é a contribuição da estratégia: escolher fronteiras que preservam as
unidades clínicas úteis ao grafo sem perder a ligação com o texto original.
