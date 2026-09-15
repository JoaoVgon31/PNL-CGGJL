# Sintagmas — POS tagging e codificação BIO

Recebe um `case_id` de `sample/cases.csv` e devolve o caso anotado em CoNLL.

```bash
python3 pos_bio.py --case-id PMC5137649_01
python3 pos_bio.py --case-id PMC5137649_01 --out caso.conll
python3 pos_bio.py --case-id PMC5137649_01 --show-pos --show-np
python3 pos_bio.py --treinar          # regera model/hmm_pos.json (único ponto que usa NLTK)
```

Um arquivo, biblioteca padrão apenas. `model/hmm_pos.json` (548 KB) é o HMM
treinado no Penn Treebank e está versionado.

## Implementação

Sete etapas sobre a mesma lista de tokens; cada uma só acrescenta informação.

| etapa | função | o que faz |
|---|---|---|
| 1 | `tokenize` | tokens com offsets de caractere; `EUS-FNA` inteiro, `12,476.5ng/ml` em dois |
| 2 | `build_constraints` | fixa a etiqueta de unidade, sigla, núcleo clínico e pontuação **antes** de decodificar |
| 3 | `HMMTagger.viterbi` | POS tagging: HMM bigrama, 12 etiquetas, Viterbi com backpointers |
| 4 | `repair_tags` | `R-premod`, `R-relverb`, `R-passiva` — erros que só se veem com a sequência pronta |
| 5 | `chunk_nps` | `NP := DET? (NUM UNIT?)? MOD* NOUN+`, depois quebra na coordenação |
| 6 | `find_spans` | tipa o bloco pelo léxico; registra sítio anatômico aninhado na camada 1 |
| 7 | `encode_bio` | IOB2, duas camadas, saída CoNLL de 4 colunas |

Palavra fora do vocabulário cai num modelo de sufixo (até 3 caracteres) com
recuo para formato gráfico, convertido para emissão por Bayes.

## Para que serve no grafo

Um grafo é feito de coisas e de ligações. No texto, as coisas são blocos de
substantivo e as ligações são os verbos entre eles — então o POS tagging é o
que separa **candidatos a nó** de **candidatos a aresta**.

O que esta etapa entrega às seguintes:

- **A fronteira do nó.** Um dicionário casa `tomography`; a gramática devolve
  `contrast enhanced computed tomography`. É a fronteira que produz o `label`.
- **Os offsets.** Cada bloco carrega `char_start`/`char_end`, o que permite
  preencher `evidence_text` das arestas e auditar a extração.
- **Os verbos isolados.** `underwent`, `revealed`, `was diagnosed with` sobram
  fora dos blocos, prontos para virar `trigger` de aresta.
- **Uma representação medível.** Um rótulo por token permite anotar casos à mão
  no mesmo formato e reportar precisão/revocação/F1.

O `label` do nó é o bloco **menos** o que virou atributo ou span aninhado:
`a 6cm cystic lesion` → `label=cystic lesion` + `size=6 cm`.

## Falhas

Medido sobre os 56 casos da amostra.

**1. Fronteira certa, tipo errado.** O léxico casa uma palavra no meio de um
nome que significa outra coisa. É o erro mais frequente.

| trecho real | saiu | deveria |
|---|---|---|
| `heart rate (HR) 56 beats/min` (PMC10106591_01) | `AnatomicalSite` | sinal vital |
| `deteriorate with heart failure` (PMC4782471_01) | `AnatomicalSite` | `Diagnosis` |
| `the American Diabetes Association` (PMC7086412_01) | `Diagnosis` | nada — é uma instituição |
| `admitted to fever ward` (PMC7718649_01) | `Symptom` | nada — é a ala do hospital |
| `removal of the first chest tube` (PMC8627357_01, 6×) | `AnatomicalSite` | `Treatment` |

**2. O bloco engole o verbo** — 38 de 1.062 blocos. O único erro que é
responsabilidade desta etapa. Em `The colonoscopy showed extensive colitis`
(PMC10521634_01) o bloco sai inteiro como um `Exam` e a aresta `REVEALS`
desaparece. Causa: `showed` tem forma de particípio, e a gramática aceita
particípio como modificador — a mesma permissão que salva
`contrast enhanced computed tomography`. As regras de reparo só cobrem verbo
depois de pronome relativo e depois de auxiliar.

**3. A negação entra no bloco** — 24 de 1.062. Em
`but no intrathecal immunoglobulin synthesis` (PMC10434843_01) o resultado é
`Medication`: o tipo veio de `immunoglobulin` e a ausência do achado virou um
remédio administrado. Polaridade não cabe numa coluna BIO — precisa de atributo
à parte, com regra de escopo de negação.

**4. Tipo ausente.** `body/tail` em PMC5137649_01 é delimitado corretamente e
não vira nó, porque não está no léxico. Na amostra: **7.480 sintagmas
identificados, 1.049 tipados — 14%**. O gargalo é a cobertura do dicionário,
não a fronteira.

**5. Escopo.** Não há correferência (`the cyst` mencionado cinco vezes gera
cinco blocos), não há atributos, não há tabela de nós nem de arestas. Este
arquivo produz o CoNLL; montar o grafo é etapa seguinte.

> Três dos quatro primeiros erros acontecem **depois** da análise sintática,
> sobre blocos que ela entregou corretos.
