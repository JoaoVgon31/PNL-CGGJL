# Relatório Técnico · Estação 5: Dados, Avaliação e Montagem
 
**Branch:** `feat/estacao-5-dados-avaliacao-montagem`  

---

## 1. Visão Geral e Responsabilidades da Estação 5

Na esteira de montagem do **Projeto 2**, a Estação 5 foi desenhada para atuar como o **hub de infraestrutura, árbitro experimental e integrador final** do grupo:

1. **Fornecimento de Dados Supervisionados (`silver/`):** Criar por supervisão fraca o material de treino, validação e teste para destravar imediatamente o desenvolvimento dos modelos de Machine Learning de toda a equipe (CRF, Classificador e Regressão/SVM).
2. **Definição da Métrica Comum Oficial (Regra 4):** Estabelecer a formulação matemática e o script oficial padronizado de Precision, Recall, F1 e Matriz de Confusão, assegurando que todas as estações tenham medições homogêneas e reproduzíveis.
3. **Curadoria do Gabarito Ouro (`gold/`):** Estruturar os starter packs, validar o alinhamento de texto, offsets e integridade referencial dos casos anotados manualmente pela equipe.
4. **Montagem do Grafo Final (`assembly/`):** Agrupar menções repetidas hierarquicamente ("um nó por coisa"), extrair dimensões clínicas em atributos, vincular conceitos MeSH e exportar em lote os arquivos canônicos `nodes.csv`, `edges.csv` e `_resumo.csv`.

```mermaid
flowchart LR
    T["case_texts.csv + P1"] --> G1["<b>1. splits.py & weak_supervision.py</b><br/>Gera silver/ (7.480 entidades, 2.009 relações)"]
    G1 --> C["Caio (CRF)<br/>ner_*.conll"]
    G1 --> L["Lucas (Classificador)<br/>silver_entidades_tipadas_*.csv"]
    G1 --> J["João (SVM/Regressão)<br/>relations_training_*.csv"]
    
    C -. entidades.csv .-> G2["<b>4. graph_builder.py & pipeline.py</b><br/>Clustering TF-IDF + Montagem Final"]
    L -. entidades_tipadas.csv .-> G2
    J -. relacoes.csv .-> G2
    
    G2 --> K(["Grafo Final<br/>nodes.csv + edges.csv"])
    
    GOLD["Gabarito Manual<br/>gold/"] --> EVAL["<b>3. evaluate.py</b><br/>Métricas Oficiais & Confronto P1 vs P2"]
    K -.-> EVAL
```

---

## 2. Implementação Técnica

### 2.1. Divisão Determinística de Casos (`splits.py`)
* Partição estrita por `case_id` fixada com `random_state=42` sobre os 56 casos clínicos da amostra:
  * **Treino:** 40 casos (~71,4%) — inclui o caso canônico `PMC5137649_01`.
  * **Validação:** 8 casos (~14,3%).
  * **Teste:** 8 casos (~14,3%).
* Garantia formal de **zero data leakage** (vazamento de dados):
  $$\text{Treino} \cap \text{Val} = \text{Treino} \cap \text{Teste} = \text{Val} \cap \text{Teste} = \emptyset$$
* O arquivo consolidado é exportado em `project2/data/splits.json`.

### 2.2. Supervisão Fraca e Datasets Silver (`weak_supervision.py`)
Processou os 56 casos clínicos combinando o analisador sintático com HMM (`pos_bio.py`) e os grafos consolidados do Projeto 1, gerando:
* **Para a Estação 2 (Caio - CRF):** Datasets no formato CoNLL de 4 colunas (`Token`, `POS`, `BIO_boundary`, `BIO_typed`) com quebras de sentença preservadas (`ner_train.conll`, `ner_val.conll`, `ner_test.conll`), além de `silver_entidades_*.csv`.
* **Para a Estação 3 (Lucas - Classificador):** `silver_entidades_tipadas_*.csv` com tipos clínicos atribuídos e códigos MeSH resolvidos via arestas `SAME_AS`.
* **Para a Estação 4 (João - SVM/Regressão):** Datasets enriquecidos `relations_training_*.csv` contendo pares positivos anotados, contexto intervening (`between_text`), distâncias em caracteres e amostragem balanceada de pares negativos (`relation=NONE`).
* **Mocks Universais:** `entidades.csv`, `entidades_tipadas.csv` e `relacoes.csv` consolidando os dados silver para permitir desacoplamento total da equipe.

### 2.3. Gestão e Validação do Gabarito Ouro (`gold_manager.py`)
* **Lista de Casos do Gabarito (`casos.txt`):** Disponibilizado em `project2/data/gold/casos.txt` com a relação explícita dos 8 casos de teste que **nunca** devem entrar no treino dos modelos de ML.
* **Guia de Anotação Oficial:** Elaborado o [`guia-anotacao.md`](guia-anotacao.md) (1 página) com as regras padronizadas de boundaries, classes, polaridade e certeza para a equipe.
* **Starter Packs:** Gerou em `project2/data/gold/cases/<case_id>/` o texto bruto com guias e CSVs pré-preenchidos a partir do *silver* para os 8 casos de teste, evitando anotação manual de offsets do zero.
* **Validador Estrito:** Audita automaticamente se `case_text[char_start:char_end] == texto`, valida se os IDs de origem e destino das relações existem em entidades e checa o vocabulário restrito de tipos, relações, polaridade e certeza.
* **Curadoria:** Foram auditados e curados com 100% de conformidade (0 erros) os dois casos atribuídos ao George:
  * `PMC9532611_01`: 11 entidades clínicas e 8 relações (corrigido corte indevido de regex do P1 `hypokalemic (1` para `hypokalemic weakness`).
  * `PMC9969157_01`: 23 entidades clínicas e 17 relações (eliminados falsos positivos de stop-words como "with" e "and" anotadas erroneamente como medicamentos).

### 2.4. Métrica Comum e Script de Avaliação (`metrics.py` e `evaluate.py`)
* **Entidades:** Precision, Recall e F1 tanto por limites exatos (`exact`) quanto por sobreposição relaxada (`overlap`).
* **Tipagem Clínica e MeSH:** Acurácia Global, Micro/Macro F1 por tipo clínico, Matriz de Confusão e acurácia de vinculação MeSH.
* **Relações e Negação:** Precision, Recall e F1 por tipo de aresta, acurácia de polaridade, **F1 dedicado de detecção de negação** (`polarity=absent`) e acurácia de certeza (`certainty=asserted`).
* **Confronto Experimental:** Função `compare_experiments()` que computa deltas absolutos ($\Delta$) e relativos (%) entre a baseline do Projeto 1 e os modelos de Machine Learning do Projeto 2.

### 2.5. Montagem do Grafo Final e Deduplicação (`clustering.py`, `graph_builder.py`, `pipeline.py`)
* **Normalização e Extração de Atributos:** Normalização Unicode NFKC, strip de determinantes iniciais e extração de medidas em atributos estruturados (ex: `6cm cystic lesion` $\rightarrow$ label `cystic lesion`, atributo `size=6 cm`).
* **Clustering de Menções Coreferentes:** Vetorização por TF-IDF de N-gramas de caracteres (`char_wb`, n-grams 2 a 4) combinada com *stem matching*. Menções do mesmo tipo clínico são agrupadas hierarquicamente (Union-Find conexo) em um único nó canônico, preservando os identificadores originais no atributo `mentions=t2|t7`.
* **Construção do Grafo:** Atribuição de identificadores canônicos (`P1`, `S1`, `E1`...), instanciação de nós `Concept` (`C1`, `C2`...) apenas para códigos MeSH válidos, e mapeamento de arestas clínicas traduzindo IDs de entidades para IDs de nós (removendo auto-loops e duplicatas).

### 2.6. Documentação Descentralizada dos Submódulos
Para atender aos critérios da issue e facilitar o uso independente por outros membros da equipe:
* [`project2/src/data/README.md`](../data/README.md): Instruções de splits, geração do silver v0 e auditoria do gabarito.
* [`project2/src/evaluation/README.md`](../evaluation/README.md): Guia com os comandos exatos de avaliação para cada membro (Caio, Lucas e João).
* [`project2/src/assembly/README.md`](../assembly/README.md): Instruções de execução do pipeline de montagem e consolidação de grafos.

---

## 3. Guia de Execução: Como Gerar os Arquivos em `project2/data/processed/`

### 3.1. Comando Padrão de Execução
Para executar a montagem e deduplicação em lote de todos os 56 casos clínicos da amostra:

```bash
python -m project2.src.assembly.pipeline
```

Ao final da execução, a pipeline imprimirá um relatório sumarizado no terminal:
```text
======================================================================
RELATORIO DE MONTAGEM DE GRAFOS EM LOTE (Estacao 5 - George)
======================================================================
Total de casos processados: 56
Casos com sucesso:          56
Casos com erro:             0
Total de nós gerados:       1393
Total de arestas geradas:   833
Resumo consolidado salvo em: project2\data\processed\_resumo.csv
======================================================================
```

### 3.2. Parâmetros Customizados (CLI)
É possível passar argumentos opcionais para alterar os arquivos de entrada, diretório de saída ou filtrar casos específicos:

```bash
python -m project2.src.assembly.pipeline \
    --entities project2/data/silver/entidades_tipadas.csv \
    --relations project2/data/silver/relacoes.csv \
    --output project2/data/processed \
    --case-ids PMC11259348_01,PMC11723754_01
```

* `--entities`: Caminho para o CSV de entidades tipadas (padrão: `project2/data/silver/entidades_tipadas.csv`).
* `--relations`: Caminho para o CSV de relações (padrão: `project2/data/silver/relacoes.csv`).
* `--output`: Pasta onde os grafos serão salvos (padrão: `project2/data/processed/`).
* `--case-ids`: Lista de `case_id`s separados por vírgula para execução parcial.

### 3.3. Artefatos Gerados em `project2/data/processed/`
A execução produzirá:
1. **`<case_id>-nodes.csv`**: Tabela de nós do caso com as colunas:
   * `node_id`: Identificador canônico (`P1`, `S1`, `E1`...).
   * `type`: Tipo clínico (`Condition`, `Medication`, `Exam`, `Concept`, etc.).
   * `label`: Rótulo consolidado e limpo da entidade.
   * `attributes`: Metadados estruturados (ex: `size=6 cm`, `mentions=t2|t5`).
2. **`<case_id>-edges.csv`**: Tabela de arestas do caso com as colunas:
   * `edge_id`: Identificador da aresta (`rel_0`, `rel_1`...).
   * `source_id` / `target_id`: Nós de origem e destino mapeados para os nós canônicos.
   * `relation`: Tipo de relação clínica (`treats`, `indicates`, `SAME_AS`, etc.).
   * `attributes`: Polaridade (`present`/`absent`) e certeza (`asserted`/`hypothetical`).
3. **`_resumo.csv`**: Tabela resumo com métricas de montagem de todos os casos processados (nós brutos, nós canônicos, arestas geradas e status).

---

### 3.4. Como Executar os Demais Módulos da Estação 5

* **Regenerar Splits de Casos (`splits.json`):**
  ```bash
  python -m project2.src.data.splits
  ```
* **Regenerar Datasets Silver (Supervisão Fraca):**
  ```bash
  python -m project2.src.data.weak_supervision
  ```
* **Executar Avaliação Oficial das Predições contra o Gabarito Ouro:**
  ```bash
  python -m project2.src.evaluation.evaluate
  ```
* **Executar Confronto Experimental Oficial (Projeto 1 vs. Projeto 2):**
  ```bash
  python -m project2.src.evaluation.evaluate --compare
  ```

---

## 4. Qualidade de Código e Testes Unitários

Para garantir a confiabilidade matemática e a estabilidade da esteira, foi desenvolvida uma suíte com **23 testes unitários** cobrindo todos os módulos da Estação 5:

```bash
pytest project2/src/
```

Resultado da execução:
```text
Ran 23 tests in 1.95s
OK (23 passed)
```

### Distribuição dos Testes:
* [`test_splits.py`](file:///c:/Users/georg/Estudos/unicamp/PNL-CGGJL/project2/src/data/tests/test_splits.py) (5 testes): Validação das proporções do split (71,4% / 14,3% / 14,3%), isolamento estrito entre conjuntos, determinismo de semente aleatória e tratamento de exceções.
* [`test_weak_supervision.py`](file:///c:/Users/georg/Estudos/unicamp/PNL-CGGJL/project2/src/data/tests/test_weak_supervision.py) (4 testes): Limpeza de determinantes, casamento exato de offsets no texto bruto, formatação CoNLL de 4 colunas e integridade de atributos.
* [`test_gold_manager.py`](file:///c:/Users/georg/Estudos/unicamp/PNL-CGGJL/project2/src/data/tests/test_gold_manager.py) (4 testes): Validador estrito de offsets contra o `case_text`, checagem de integridade referencial entre entidades e relações e consolidação do manifesto.
* [`test_metrics.py`](file:///c:/Users/georg/Estudos/unicamp/PNL-CGGJL/project2/src/evaluation/tests/test_metrics.py) (5 testes): Casamento de boundary (exato vs. overlap), métricas multiclasse de tipos clínicos, acurácia de MeSH, F1 dedicado de negação e cálculo de deltas comparativos.
* [`test_assembly.py`](file:///c:/Users/georg/Estudos/unicamp/PNL-CGGJL/project2/src/assembly/tests/test_assembly.py) (5 testes): Normalização de strings e case folding, extração de dimensões em atributos, agrupamento hierárquico por similaridade de texto, geração de nós Concept e execução do pipeline em lote.

---

## 5. Resultados Quantitativos e Métricas

### 5.1. Estatísticas do Dataset Silver (Supervisão Fraca)
* **Casos processados:** 56 casos clínicos da amostra.
* **Entidades supervisionadas:** 7.480 entidades.
  * Treino: 6.019 (~80,5%)
  * Validação: 879 (~11,7%)
  * Teste: 582 (~7,8%)
* **Relações supervisionadas:** 2.009 relações anotadas.

### 5.2. Estatísticas dos Grafos Consolidados (`processed/`)
* **Casos montados com sucesso:** 56 de 56 (100% de sucesso).
* **Total de nós canônicos gerados:** 1.393 nós.
* **Total de arestas clínicas e conceituais geradas:** 833 arestas.

### 5.3. Avaliação Experimental do Baseline (Projeto 1) contra o Gabarito Ouro
Utilizando o framework do `evaluate.py` para comparar o baseline de regras contra os casos de teste do Gabarito Ouro anotados manualmente:

| Tarefa Avaliada | Precision | Recall | F1-Score | Destaques da Análise |
|---|:---:|:---:|:---:|---|
| **Boundary de Entidades (Exato)** | 71,99% | **96,77%** | **82,56%** | As regras capturam quase todas as menções, mas pecam por incluir pontuação e determinantes nas bordas. |
| **Boundary de Entidades (Overlap)**| **92,15%** | **98,90%** | **95,41%** | Quando relaxada a sobreposição, o alinhamento com o gabarito ouro atinge mais de 95% de F1. |
| **Classificação de Tipos Clínicos** | 96,66% (Acurácia) | — | 73,10% (Macro F1) | Classes frequentes (`Exam`, `AnatomicalSite`) atingiram F1 = 1,0; classes mais raras sofreram com o desbalanceamento das regras. |
| **Vinculação Conceitual MeSH** | 60,87% (Acurácia) | — | — | Os dicionários do Projeto 1 cobrem termos estritamente idênticos, mas têm dificuldade com sinônimos e paráfrases. |
| **Relações Clínicas** | — | **70,93%** | — | 61 das 86 arestas ouro foram recuperadas com sucesso pelas heurísticas do P1. |
| **Detecção de Negação** | **100,00%** | **100,00%** | **1,0000** | A lista de proteção de negação acertou todas as menções ausentes (`polarity=absent`) sem nenhum falso positivo. |

---

## 6. Conclusões e Próximos Passos

1. **Eficiência da Infraestrutura Desacoplada:** A criação imediata dos mocks e datasets *silver* na Fase 1 permitiu que os colegas de equipe que implementam modelos de Machine Learning (Caio com CRF, Lucas com Classificador e João com SVM/Regressão) iniciassem os treinos sem bloqueios de interdependência.
2. **Qualidade do Agrupamento Hierárquico:** O algoritmo de clustering desenvolvido para o `graph_builder.py` resolveu com elegância o problema de "um nó por coisa", agrupando coreferências textuais (ex: *"cystic lesion"*, *"the lesion"*, *"6cm cystic lesion"*) em um único nó canônico sem perda de atributos clínicos.
3. **Ponto de Partida Forte para o Projeto 2:** Os resultados do baseline comprovam que os modelos de Machine Learning têm margem clara para superar as regras principalmente na **Precisão de fronteira** (eliminando ruídos com CRF) e na **Vinculação Conceitual MeSH** (generalizando além do matching exato de strings).
4. **Fechamento Final (Fase 5):** A Estação 5 está **100% pronta e testada**. Assim que os demais integrantes finalizarem suas predições (`entidades.csv`, `entidades_tipadas.csv` e `relacoes.csv`), bastará:
   * Executar `python -m project2.src.assembly.pipeline` apontando para as predições de ML para gerar o grafo final do Projeto 2 em `project2/data/processed/`.
   * Executar `python -m project2.src.evaluation.evaluate --compare` para emitir o confronto experimental definitivo para o relatório final do grupo.
