# Avaliação — Métricas de Menções, Tipos, Relações e Grafos (#29)

Módulo unificado de avaliação do Projeto 2 (`project2/src/avaliacao/avaliar.py`), utilizado pelas Etapas 2, 3, 4 e na comparação final dos grafos montados.

## Funções e Métricas

1. **`avaliar_mencoes(pred, gold)`**:
   - Calcula precisão, revocação e F1 de fronteiras de menções em dois modos (pareamento 1-para-1 por caso):
     - `exato`: mesmo início e fim `(start, end)`.
     - `sobreposicao`: qualquer interseção de caracteres `start_p < end_g and start_g < end_p`.
2. **`avaliar_tipos(pred, gold, exato=True)`**:
   - Calcula `cobertura`, `acuracia`, `macro_f1`, métricas `por_tipo` (`precisao`, `revocacao`, `f1`, `n`), matriz de `confusao` e métricas de negação/polaridade (`acuracia_polaridade` e `f1_absent`).
3. **`avaliar_relacoes(pred_rel, gold_rel, pred_mencoes, gold_mencoes, exato=True)`**:
   - Avalia relações casando os extremos pelos spans `(start, end)` das menções (ou `P1` quando a origem é o paciente), nunca por IDs internos.
   - Suporta avaliação **isolada** (`pred_mencoes == gold_mencoes`) e **ponta a ponta** (`pred_mencoes` vindas do CRF).
4. **`avaliar_grafo(pasta_grafos)`**:
   - Métricas estruturais dos grafos `<case_id>-nodes.csv` e `<case_id>-edges.csv`: número de nós e arestas, grau médio, % de nós clínicos com código MeSH e contagem de nós duplicados com o mesmo código MeSH no mesmo caso.

## Uso via Linha de Comando

```bash
python project2/src/avaliacao/avaliar.py mencoes --pred project2/data/mencoes.csv --gold project2/data/gold/mencoes.csv
python project2/src/avaliacao/avaliar.py tipos --pred project2/data/mencoes_tipadas.csv --gold project2/data/gold/mencoes.csv
python project2/src/avaliacao/avaliar.py relacoes --pred project2/data/relacoes.csv --gold project2/data/gold/relacoes.csv --mencoes-pred project2/data/mencoes_tipadas.csv --mencoes-gold project2/data/gold/mencoes.csv
python project2/src/avaliacao/avaliar.py grafo --pasta project2/data/grafos
```
