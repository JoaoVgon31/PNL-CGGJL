# Projeto `Extração Estatística e por Aprendizado de Máquina de Grafos de Conhecimento de Casos Clínicos do MultiCaRe`
# Project `Statistical and Machine Learning Extraction of Knowledge Graphs from MultiCaRe Clinical Cases`

Equipe `CGGJL`: Caio Melloni (167974), Gabriel Lorhan Rodrigues Dourado (197496), George Henrique de Lima Sá (231529), João Vitor Gonçalves Oliveira (237871) e Lucas Guarnieri (119756).

## Slides

[Apresentação do Projeto 2 (PDF)](assets/slides/CGGJL-P2.pdf)

## Demonstração Executável

O [visualizador interativo](data/visualizador/README.md) do Projeto 1 foi reaproveitado. Ele mostra os grafos gerados pelo Projeto 2 caso a caso, e cada nó e aresta tem sua evidência destacada no `case_text` original. Para gerar e abrir o visualizador, rode a partir da raiz do repositório:

~~~bash
python -m project2.src.montagem.montagem --visualizador project2/data/visualizador
python -m http.server 8000 --directory project2/data/visualizador
# abrir http://localhost:8000
~~~

A demonstração passo a passo e inspeção dos resultados também pode ser executada no notebook [`pipelines/notebooks/pipeline_projeto2.ipynb`](pipelines/notebooks/pipeline_projeto2.ipynb). As instruções de instalação e a execução completa do pipeline via CLI estão em [`src/README.md`](src/README.md).

## Metodologia

O Projeto 2 mantém o objetivo do [Projeto 1](../project1/README.md): transformar o `case_text` de cada caso do MultiCaRe em um grafo (`<case_id>-nodes.csv` e `<case_id>-edges.csv`, no mesmo contrato do P1). A diferença é que as regras escritas à mão dão lugar a estatística de N-gramas e a aprendizado de máquina clássico. Nenhum LLM, *embedding* neural ou Transformer participa da extração.

O pipeline tem cinco etapas, ligadas por tabelas CSV em `data/`. Cada etapa pode ser avaliada de duas formas:

* **Isolada:** recebe as menções do gabarito manual.
* **Ponta a ponta:** recebe a saída real da etapa anterior.

~~~mermaid
flowchart LR
    C["Casos (56)"] --> S["Etapa 5: silver<br/>regras P1 nos casos não-gold"]
    C --> T["Etapa 1: termos<br/>PMI + C-value"]
    S --> E["Etapa 2: CRF<br/>mencoes.csv"]
    T --> E
    E --> Y["Etapa 3: léxico + LR<br/>mencoes_tipadas.csv"]
    S --> Y
    Y --> R["Etapa 4: regra P1 + LR<br/>relacoes.csv"]
    S --> R
    Y --> M["Montagem<br/>grafo/*.csv"]
    R --> M
    G["Gabarito (8 casos)"] --> A["Etapa 5: avaliação<br/>resultados/*.csv"]
    E --> A
    Y --> A
    R --> A
    M --> A
~~~

### Divisão de Responsabilidades por Issue

| Etapa | Issue | Responsável | Código | Saída |
|---|---|---|---|---|
| **Etapa 1: Termos e Montagem** | [#32](https://github.com/caiomelloni/PNL-CGGJL/issues/32) | Gabriel Lorhan R. Dourado | [`src/comum`](src/comum/), [`src/termos`](src/termos/), [`src/montagem`](src/montagem/) | `data/termos.csv`, `data/associacoes.csv`, `data/grafo/` |
| **Etapa 2: Fronteiras de Menções** | [#33](https://github.com/caiomelloni/PNL-CGGJL/issues/33) | Caio Melloni | [`src/entidades`](src/entidades/) | `data/mencoes.csv` |
| **Etapa 3: Tipos, Conceito e Polaridade** | [#34](https://github.com/caiomelloni/PNL-CGGJL/issues/34) | Lucas Guarnieri | [`src/tipos`](src/tipos/) | `data/mencoes_tipadas.csv` |
| **Etapa 4: Relações** | [#35](https://github.com/caiomelloni/PNL-CGGJL/issues/35) | João Vitor G. Oliveira | [`src/relacoes`](src/relacoes/) | `data/relacoes.csv` |
| **Etapa 5: Silver, Gabarito e Avaliação** | [#29](https://github.com/caiomelloni/PNL-CGGJL/issues/29) | George Henrique de Lima Sá | [`src/dados`](src/dados/), [`src/avaliacao`](src/avaliacao/) | `data/silver/`, `data/gold/`, `data/resultados/` |

**Dados: silver e gabarito.** A amostra tem 56 casos:

* **Gabarito (8 casos):** listados em [`data/gold/casos.txt`](data/gold/casos.txt) e anotados à mão, com 224 menções e 193 relações ([`data/gold/`](data/gold/)). Esses casos nunca entram no treino.
* **Silver (48 casos restantes):** [`src/dados/silver.py`](src/dados/silver.py) roda as regras do P1 nesses casos e grava os offsets exatos. O resultado tem 799 menções (em 45 casos), 567 relações e 1.366 frases em BIO (`data/silver/`), que servem de treino supervisionado fraco.

**Etapa 1 — termos compostos.** [`src/termos/termos.py`](src/termos/termos.py) conta N-gramas de 2 a 4 palavras e aplica três critérios:

* **Filtro de classe gramatical:** usa o POS do HMM do P1. O termo não pode cruzar pontuação nem fronteira de frase.
* **PMI:** mede a coesão entre as palavras do termo.
* **C-value:** desconta termos que só aparecem dentro de termos maiores.

Como diferencial, `associar` calcula o PMI entre pares de códigos MeSH que aparecem nos mesmos casos do silver ([`data/associacoes.csv`](data/associacoes.csv)).

~~~python
# C-value: penaliza o candidato pela frequência média dos termos maiores que o contêm
math.log2(len(a)) * (f - somas[a] / quantidades[a] if quantidades[a] else f)
~~~

**Etapa 2 — fronteiras com CRF.** [`src/entidades/entidades.py`](src/entidades/entidades.py) trata a detecção de menções como rotulagem BIO sem tipo. O modelo é um CRF linear (`sklearn-crfsuite`), com $c_1$ e $c_2$ escolhidos por busca em grade em 20% dos casos silver. As features de cada palavra são:

* a palavra, seus prefixos e sufixos e o formato (`Xxxx`, `dd-xx`);
* a classe gramatical do HMM;
* uma janela de ±2 palavras;
* na variante `--termos`, a marca de pertencer a um termo de `termos.csv`.

**Etapa 3 — tipo, conceito e polaridade.** [`src/tipos/tipos.py`](src/tipos/tipos.py) trabalha em cascata:

1. O léxico do P1 e os gazetteers MeSH e `AnatomicalSite` dão o tipo e o código. Siglas definidas no próprio caso, no padrão `forma extensa (SIGLA)`, herdam o tipo e o código da forma extensa.
2. Menções desconhecidas ou ambíguas vão para uma `LogisticRegression` (`class_weight="balanced"`). Ela usa TF-IDF de N-gramas de caracteres (2–5) e de palavras (1–2) da menção, mais as palavras vizinhas marcadas com o lado em que aparecem.
3. A polaridade é decidida só pela oração que antecede a menção, e não pela frase inteira como no P1:

~~~python
cortes = list(_CORTE_CLAUSULA.finditer(texto_caso, s_ini, inicio))  # ; : but however although whereas
inicio_oracao = cortes[-1].end() if cortes else s_ini
return detect_polarity(texto_caso[inicio_oracao:inicio])
~~~

**Etapa 4 — relações.** [`src/relacoes/relacoes.py`](src/relacoes/relacoes.py) separa as relações em dois grupos:

* **Relações do paciente** (`HAS_SYMPTOM`, `UNDERWENT_EXAM`, `DIAGNOSED_WITH`, `TREATED_WITH`, `HAS_OUTCOME`, `HAS_HISTORY`, `HAS_FINDING`): saem de uma regra fixa pelo tipo da menção.
* **Relações entre menções** (`HAS_RESULT`, `REVEALS`, `LOCATED_IN`, `SUPPORTS`, `TREATED_WITH`): um classificador avalia os pares a até 200 caracteres. As features são TF-IDF de N-gramas (1-1, 1-2 e 1-3) do texto entre as menções, os tipos, a distância e a ordem das menções. Só entram pares que o domínio da ontologia permite.

`LogisticRegression` e `LinearSVC` foram comparados. A saída usa `LogisticRegression`, porque ela fornece a probabilidade que vai para o atributo `confianca` da aresta.

~~~python
if rel_pred == "NONE" or rel_pred not in relacoes_permitidas(row["source_type"], row["target_type"]):
    continue  # nunca emite uma aresta fora do domínio aceito pela montagem
~~~

**Montagem.** [`src/montagem/montagem.py`](src/montagem/montagem.py) valida os contratos e funde menções do mesmo caso com o mesmo tipo, a mesma polaridade e o mesmo código MeSH (ou o mesmo rótulo normalizado). Medidas em mm/cm saem do rótulo e vão para o atributo `size`. Para cada código, a montagem cria um nó `Concept` com arestas `SAME_AS`. Cada nó e cada aresta guardam as menções de origem, os spans e o `evidence_text`.

### Confronto com Trabalho Anterior

As duas versões foram medidas no mesmo gabarito de 8 casos. A tabela completa está em [Resultados](#resultados).

* **Tipos e relações:** dadas as menções corretas (modo isolado), o P2 é muito superior.
  * Tipos: o Macro-F1 vai de 0,21 para 0,62.
  * Relações: o F1 vai de 0,10 para 0,75.
  * O P1 deixava sem tipo a maior parte das menções que encontrava. A cascata do P2 dá tipo a todas.
* **Fronteiras das menções:** este é o gargalo do P2. O CRF foi treinado num silver produzido pelas próprias regras do P1, que deixam muitas menções reais rotuladas como `O`. O resultado é um modelo preciso e conservador:
  * precisão de 0,93 por sobreposição;
  * apenas 28 menções previstas, contra 224 no gabarito.

  No modo ponta a ponta, esse baixo recall se propaga, e o P2 fica abaixo do P1 em F1 de tipos e relações.
* **Negação:** um erro conhecido do P1 era *"no mucosal abnormalities"* ficar como presente. No grafo do P2 do caso `PMC5137649_01`, essa menção sai com `polarity=absent`, e a aresta `endoscopy -REVEALS-> mucosal abnormalities` traz a evidência *"endoscopy was performed and no mucosal abnormalities"*.
* **Grafo:** nos 56 casos, a fração de nós clínicos ligados a um código MeSH/`ANAT` sobe de 26,6% para 40,5%. Os nós duplicados com o mesmo código no mesmo caso caem de 8 para 3.

## Trabalhos Estudados

* **Church & Hanks (1990)** — PMI como medida de associação entre palavras. Usado na coesão dos termos compostos e nas associações entre conceitos MeSH.
* **Frantzi, Ananiadou & Mima (2000)** — C-value para termos multipalavra. Motivou o desconto de termos aninhados, como `cell count` dentro de `white blood cell count`.
* **Lafferty, McCallum & Pereira (2001)** — CRF para rotulagem de sequências. É a base da Etapa 2.
* **Nievas Offidani et al. (2025)** — descreve o MultiCaRe, o corpus usado.
* **MeSH (NLM)** — vocabulário controlado dos nós `Concept`, herdado do P1.

## Modelo Lógico

O modelo de grafo de propriedades é o mesmo do P1:

* 10 tipos de entidade clínica;
* o nó `Patient` (`P1`);
* nós `Concept` ligados por `SAME_AS`.

O P2 acrescenta atributos de rastreabilidade (`mentions`, `spans`, `evidence_spans`) e o atributo `confianca` nos nós e arestas.

![Modelo lógico do grafo de conhecimento clínico](assets/images/modelo-logico.svg)

## Análises que podem ser realizadas

* **Filtrar por confiança.** Toda aresta prevista pelo classificador tem `confianca`. É possível montar um grafo só com relações acima de um limiar e comparar a precisão obtida.
* **Associações entre conceitos.** O grafo de associações (`data/resultados/associacoes-{nodes,edges}.csv`) liga códigos MeSH que coocorrem mais do que o acaso, por exemplo `Eye Abnormalities` ↔ `Magnetic Resonance Imaging` (PMI = 3,17).
* **Casos por conceito.** Com `SAME_AS`, grafias e siglas diferentes convergem para o mesmo código, o que permite agrupar casos por doença, exame ou fármaco.
* **Cadeias de evidência.** O caminho `Exam -REVEALS-> Finding -SUPPORTS-> Diagnosis`, filtrado por `polarity`, separa achados confirmados de achados descartados.
* **Auditoria.** Os spans e o `evidence_text` permitem conferir cada nó e cada aresta no texto original.

## Ferramentas

| Ferramenta | Uso |
|---|---|
| Python 3.10+ (`re`, `csv`, `sqlite3`, `unicodedata`) | Base do pipeline. As contagens de N-gramas usam SQLite em disco |
| scikit-learn | `TfidfVectorizer`, `LogisticRegression`, `LinearSVC` e `ColumnTransformer` (Etapas 3 e 4) |
| sklearn-crfsuite | CRF linear da Etapa 2 |
| pandas | Pares de relações e tabelas de resultados |
| NLTK / HMM do Projeto 1 | Frases e classe gramatical |
| rapidfuzz | Casamento aproximado com os gazetteers (herdado do P1) |
| MeSH 2026 + gazetteer `AnatomicalSite` | Códigos dos nós `Concept` |
| Cytoscape.js | Visualizador interativo (reaproveitado do P1) |
| `unittest` | 104 testes automatizados, em [`tests/`](tests/) e em `src/*/tests` |

## Resultados

Todas as métricas foram calculadas nos 8 casos do gabarito e estão em [`data/resultados/`](data/resultados/).

**Etapa 1 — termos.** Foram extraídos 584 termos compostos ([`data/termos.csv`](data/termos.csv)). Do top-100:

* 22 estão no MeSH, como `physical examination`, `white blood cell count`, `erythrocyte sedimentation rate` e `magnetic resonance imaging`.
* 78 são candidatos fora do MeSH, como `intensive care unit`, `past medical history` e `left main bronchus`, e também ruído como `normal range`.

Esse número mede cobertura lexical, não precisão.

**Etapa 2 — fronteiras** ([`entidades.csv`](data/resultados/entidades.csv)). O gabarito tem 224 menções.

| Sistema | P (exato) | R (exato) | F1 (exato) | P (sobrep.) | R (sobrep.) | F1 (sobrep.) | Previstas |
|---|---:|---:|---:|---:|---:|---:|---:|
| Regras P1 | 0,370 | 0,089 | 0,144 | 0,778 | 0,188 | 0,302 | 54 |
| Só `pos_bio` (sintagmas do P1) | 0,364 | **0,143** | **0,205** | 0,818 | **0,321** | **0,462** | 88 |
| CRF | **0,429** | 0,054 | 0,095 | **0,929** | 0,116 | 0,206 | 28 |
| CRF + termos | **0,429** | 0,054 | 0,095 | **0,929** | 0,116 | 0,206 | 28 |

A pista de termos não ajudou:

* Na validação silver, o F1 exato caiu de 0,491 (CRF) para 0,473 (CRF + termos). Por isso `mencoes.csv` vem do CRF sem termos.
* No gabarito, as duas variantes são idênticas.

**Etapa 3 — tipos e polaridade** ([`tipos.csv`](data/resultados/tipos.csv)).

| Sistema | Entrada | Casamento | Cobertura | Acurácia | Macro-F1 | Acurácia polaridade | F1 `absent` |
|---|---|---|---:|---:|---:|---:|---:|
| Regras P1 | regras | exato | 0,125 | 0,121 | 0,213 | 1,000 | 1,000 |
| Só léxico | gabarito | exato | 0,638 | 0,446 | 0,475 | 0,951 | 0,732 |
| Só classificador | gabarito | exato | 1,000 | 0,464 | 0,482 | 0,951 | 0,732 |
| **Léxico + classificador** | gabarito | exato | **1,000** | **0,603** | **0,619** | 0,951 | 0,732 |
| Léxico + classificador | CRF | sobreposição | 0,116 | 0,103 | 0,191 | 1,000 | 1,000 |

* **Confusões mais frequentes** ([`tipos_confusao.csv`](data/resultados/tipos_confusao.csv)): `Finding` previsto como `Diagnosis` (19) e `Symptom` previsto como `Diagnosis` (14). São categorias cuja fronteira depende do contexto clínico.
* **Polaridade do P1:** o 1,000 foi medido só sobre as poucas menções que o P1 encontrou. Por isso não é comparável com a polaridade medida sobre as 224 menções do gabarito.

**Etapa 4 — relações** ([`relacoes.csv`](data/resultados/relacoes.csv)). O gabarito tem 193 relações.

| Sistema | Entrada | Critério | P | R | F1 | Macro-F1 |
|---|---|---|---:|---:|---:|---:|
| Regras P1 | regras | exato | 0,220 | 0,067 | 0,103 | 0,140 |
| Regras P1 | regras | sobreposição | 0,644 | 0,197 | **0,302** | 0,288 |
| **LR (1-2) + regra do paciente** | gabarito | exato | **0,678** | **0,839** | **0,750** | **0,719** |
| LR (1-2) + regra do paciente | CRF + tipos | exato | 0,370 | 0,052 | 0,091 | 0,099 |
| LR (1-2) + regra do paciente | CRF + tipos | sobreposição | **0,815** | 0,114 | 0,200 | 0,184 |

* **N-gramas 1-1, 1-2 e 1-3:** dão resultados idênticos no gabarito.
* **Validação silver** ([`relacoes_modelos.csv`](data/resultados/relacoes_modelos.csv)): o `LinearSVC` teve Macro-F1 maior (0,79 contra 0,73 da `LogisticRegression`), mas não fornece probabilidades.
* **F1 por relação no modo isolado:**
  * acima de 0,97: `HAS_SYMPTOM` (1,00), `HAS_OUTCOME` (1,00), `TREATED_WITH` (0,98) e `UNDERWENT_EXAM` (0,97);
  * intermediário: `DIAGNOSED_WITH` (0,76), `HAS_RESULT` (0,68), `HAS_FINDING` (0,63), `REVEALS` (0,61) e `LOCATED_IN` (0,48);
  * `SUPPORTS` (0,07): só tem 1 exemplo no gabarito.

**Comparação P1 × P2** ([`comparativo_p1_p2.csv`](data/resultados/comparativo_p1_p2.csv), [`montagem.csv`](data/resultados/montagem.csv)).

| Dimensão | Modo | P1 | P2 |
|---|---|---:|---:|
| Fronteiras — F1 sobreposição | ponta a ponta | **0,302** | 0,206 |
| Tipos — Macro-F1 | isolado | 0,213 | **0,619** |
| Tipos — Macro-F1 (sobreposição) | ponta a ponta | **0,285** | 0,191 |
| Relações — F1 | isolado | 0,103 | **0,750** |
| Relações — F1 (sobreposição) | ponta a ponta | **0,302** | 0,200 |
| Grafo (56 casos) — nós clínicos com código | estrutural | 26,6% | **40,5%** |
| Grafo (56 casos) — duplicatas de mesmo código | estrutural | 8 | **3** |

Os modelos das Etapas 3 e 4 são claramente melhores que as regras quando recebem as menções certas. O recall da Etapa 2 é o que limita o pipeline completo. O próximo passo natural é melhorar esse recall, por exemplo:

* treinando o CRF no corpus completo;
* filtrando do silver as frases sem nenhuma menção, que são as que mais carregam falsos `O`;
* combinando o recall do `pos_bio` com o classificador da Etapa 3.

**Exemplo de grafo** (trecho de `PMC5137649_01`, [nós](data/grafo/PMC5137649_01-nodes.csv) e [arestas](data/grafo/PMC5137649_01-edges.csv)). O grafo completo tem 45 nós e 55 arestas. Os números nas arestas são a confiança do classificador.

~~~mermaid
flowchart LR
    P1(["Patient P1"]) -->|UNDERWENT_EXAM| E2["Exam: EUS-FNA"]
    P1 -->|UNDERWENT_EXAM| E6["Exam: endoscopy"]
    P1 -->|DIAGNOSED_WITH| D4["Diagnosis: GDC"]
    E2 -->|"REVEALS 0.96"| F1["Finding: cyst (4 menções)"]
    E6 -->|"REVEALS 0.97"| F4["Finding: mucosal abnormalities (absent)"]
    F1 -->|"LOCATED_IN 0.99"| A2["AnatomicalSite: stomach"]
    F1 -->|"SUPPORTS 0.99"| D4
    F1 -->|SAME_AS| C7["Concept D003560"]
~~~

## Como Modelos de Linguagem foram Usados

Modelos de linguagem **não** participam da extração, do treino nem da inferência. O pipeline usa apenas regex, HMM, estatística de N-gramas, CRF e classificadores lineares.

Assistentes de IA (Claude e Gemini) foram usados no apoio à programação:

* revisão do código entre as etapas;
* escrita de testes;
* redação da documentação.

A curadoria do gabarito e a validação dos resultados foram feitas pelos integrantes do grupo.

## Referências Bibliográficas

* Church, K. W., & Hanks, P. (1990). Word association norms, mutual information, and lexicography. *Computational Linguistics*, 16(1), 22–29.
* Frantzi, K., Ananiadou, S., & Mima, H. (2000). Automatic recognition of multi-word terms: the C-value/NC-value method. *International Journal on Digital Libraries*, 3(2), 115–130.
* Lafferty, J., McCallum, A., & Pereira, F. C. N. (2001). Conditional random fields: Probabilistic models for segmenting and labeling sequence data. *Proceedings of ICML 2001*, 282–289.
* Nievas Offidani, M., Roffet, F., González Galtier, M. C., Massiris, M., & Delrieux, C. (2025). An Open-Source Clinical Case Dataset for Medical Image Classification and Multimodal AI Applications. *Data*, 10(8), 123. https://doi.org/10.3390/DATA10080123
* National Library of Medicine. *MeSH XML Data Files*. https://www.nlm.nih.gov/mesh/xmlmesh.html
* Okazaki, N. (2007). CRFsuite: a fast implementation of Conditional Random Fields. https://www.chokkan.org/software/crfsuite/
* Pedregosa, F. et al. (2011). Scikit-learn: Machine Learning in Python. *Journal of Machine Learning Research*, 12, 2825–2830.
* Santanchè, A. *nlp2learn — Projeto 2 (2026)*. https://github.com/santanche/nlp2learn/tree/main/projects/2026/project2
