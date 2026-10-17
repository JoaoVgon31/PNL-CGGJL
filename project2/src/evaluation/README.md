# Módulo de Avaliação e Métricas (`project2/src/evaluation/`)

Este módulo é o **árbitro experimental oficial** do Projeto 2. Ele implementa as formulações matemáticas padronizadas de Precision, Recall, F1-Score, Matriz de Confusão e confronto com a baseline de regras do Projeto 1.

---

## Como Avaliar Cada Estação

Cada membro do grupo avalia suas predições contra o gabarito ouro usando um único comando:

### 1. Avaliação de Entidades / Limites (Estação 2 · Caio)
```bash
# Avaliação estrita por limites exatos (boundary exato):
python -m project2.src.evaluation.evaluate --task entities --pred caminho/para/suas_entidades.csv --match-mode exact

# Avaliação com sobreposição relaxada (overlap):
python -m project2.src.evaluation.evaluate --task entities --pred caminho/para/suas_entidades.csv --match-mode overlap
```

### 2. Avaliação de Tipos Clínicos e MeSH (Estação 3 · Lucas)
```bash
python -m project2.src.evaluation.evaluate --task types --pred caminho/para/suas_entidades_tipadas.csv
```
* Emite Macro/Micro F1, Acurácia Global, Matriz de Confusão e acurácia de vinculação aos códigos conceituais MeSH.

### 3. Avaliação de Relações e Negação (Estação 4 · João)
```bash
python -m project2.src.evaluation.evaluate --task relations --pred caminho/para/suas_relacoes.csv
```
* Emite Precision, Recall e F1 por tipo de relação clínica, acurácia de polaridade/certeza e o **F1 dedicado de detecção de negação** (`polarity=absent`).

---

## Confronto Experimental Oficial (Projeto 1 vs. Projeto 2)

Para comparar o ganho dos modelos de Machine Learning sobre as regras do Projeto 1:

```bash
python -m project2.src.evaluation.evaluate --compare \
    --pred project2/data/silver/entidades_tipadas.csv \
    --baseline project2/data/silver/entidades.csv \
    --gold project2/data/gold/gold_entidades.csv
```
* O script calcula automaticamente os deltas absolutos ($\Delta$) e percentuais entre a baseline de regras e o modelo estatístico.
