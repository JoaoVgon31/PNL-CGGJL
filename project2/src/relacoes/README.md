# Etapa 4 — Relações entre entidades (Issue #35)

Infere relações clínicas entre entidades combinando uma regra fixa (pares envolvendo o paciente `P1`) com um classificador de N-gramas (demais pares compatíveis com a ontologia).
As decisões de projeto estão em [docs/relacoes.md](../../docs/relacoes.md).

## Como rodar

Esta Etapa consome o corpus silver (`project2/data/silver/mencoes.csv`), as menções tipadas da Etapa 3 (`project2/data/mencoes_tipadas.csv`) e o gabarito consolidado (`project2/data/gold/`).

**Todos os comandos abaixo devem ser rodados a partir da raiz do repositório** (`PNL-CGGJL/`):

```bash
# 1. Gera os pares de treino/val/test a partir do silver (excluindo os 8 casos gold)
python -m project2.src.relacoes.mock.gerar

# 2. Treina o classificador de relacoes e salva project2/models/relacoes/classificador.pkl
python -m project2.src.relacoes.relacoes treinar

# 3. Avalia nos 8 casos gold (isolado e ponta a ponta) e gera data/relacoes.csv + data/resultados/relacoes.csv
python -m project2.src.relacoes.relacoes comparar

# 4. Prediz relacoes sobre data/mencoes_tipadas.csv
python -m project2.src.relacoes.relacoes prever

# 5. Roda a suite de testes da Etapa 4
python -m unittest discover -s project2/src/relacoes -v
```

### Saídas geradas

- `project2/models/relacoes/classificador.pkl`: pipeline `LogisticRegression` vencedor treinado nos pares silver não-gold.
- `project2/data/relacoes.csv`: predições finais nos 56 casos no contrato `case_id,origem,destino,relacao,confianca` consumido por `project2/src/montagem/montagem.py`.
- `project2/data/resultados/relacoes.csv`: avaliação nos 8 casos do gabarito (`regras P1` vs. `LR (1-1)`, `LR (1-2)` e `LR (1-3)`) tanto em modo **isolado** (`entrada=gabarito`) quanto **ponta a ponta** (`entrada=crf+tipos`), global e por tipo de relação.
- `project2/data/resultados/relacoes_modelos.csv`: comparação em validação silver entre `LogisticRegression` e `LinearSVC` para `(1, 1)`, `(1, 2)` e `(1, 3)`-gramas.

## Arquitetura

1. **Regra de paciente** (`apply_patient_rule` / `PATIENT_RELATION_MAP`): menções dos tipos `Symptom→HAS_SYMPTOM`, `Exam→UNDERWENT_EXAM`, `Diagnosis→DIAGNOSED_WITH`, `Outcome→HAS_OUTCOME`, `Medication/Treatment→TREATED_WITH`, `History→HAS_HISTORY` e `Finding→HAS_FINDING` (quando o `Finding` não é alvo de `REVEALS`) recebem aresta partindo de `P1` com `confianca = 1.0`.
2. **Classificador de N-gramas**: para os demais pares compatíveis com o domínio (`HAS_RESULT`, `REVEALS`, `LOCATED_IN`, `SUPPORTS`, `TREATED_WITH`, `NONE`) em janela de até 200 caracteres, um `Pipeline` do `scikit-learn` combina TF-IDF de `between_text`, one-hot de `(source_type, target_type)`, `distance_chars` e `source_before_target`.
3. O modelo de produção é `LogisticRegression` (fornece `predict_proba` nativo para `confianca`). Para relações funcionais no alvo (`HAS_RESULT`, `REVEALS`, `LOCATED_IN`), cada menção-alvo é associada à menção-origem compatível mais próxima/confiante na janela.
