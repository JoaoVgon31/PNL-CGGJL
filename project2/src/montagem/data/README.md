# Módulo de Dados (`project2/src/montagem/data/`)

Este módulo gerencia a partição dos casos clínicos, a geração de dados por supervisão fraca (*Silver Standard*) e a consolidação/validação do gabarito ouro anotado manualmente (*Gold Standard*).

---

## Como Executar

### 1. Partição Determinística de Casos (`splits.py`)
Gera a divisão reprodutível dos 56 casos clínicos da amostra com garantia de **zero data leakage** ($\text{Treino} \cap \text{Val} = \text{Treino} \cap \text{Teste} = \emptyset$):

```bash
python -m project2.src.montagem.data.splits
```
* **Saída:** [`project2/data/splits.json`](file:///c:/Users/georg/Estudos/unicamp/PNL-CGGJL/project2/data/splits.json) (40 treino, 8 validação, 8 teste).

---

### 2. Geração do Dataset Silver por Supervisão Fraca (`weak_supervision.py`)
Executa o rotulador automático baseado nas regras do Projeto 1 e no HMM/sintagmas:

```bash
python -m project2.src.montagem.data.weak_supervision
```
* **Tempo de execução aproximado:** ~40 segundos.
* **Saídas geradas em `project2/data/silver/`:**
  * `ner_train.conll`, `ner_val.conll`, `ner_test.conll` (para CRF - Caio).
  * `silver_entidades_tipadas_*.csv` (para Classificador de Tipos e MeSH - Lucas).
  * `relations_training_*.csv` com pares positivos e negativos balanceados (para SVM/Regressão - João).
  * `entidades.csv`, `entidades_tipadas.csv` e `relacoes.csv` (mocks globais consolidados).

---

### 3. Consolidação e Validação do Gabarito Ouro (`gold_manager.py`)
Audita a consistência dos casos de teste anotados manualmente em `project2/data/gold/cases/<case_id>/`:

```bash
# Valida offsets de texto, vocabulário e integridade referencial
python -m project2.src.montagem.data.gold_manager
```
* **Saídas geradas em `project2/data/gold/`:**
  * `gold_entidades.csv`
  * `gold_relacoes.csv`
  * `manifest.json`
