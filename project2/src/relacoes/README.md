# Etapa 4 — Relações entre entidades (Issue #35)

Infere relações clínicas entre entidades combinando uma regra fixa (pares
envolvendo o paciente) com um classificador de N-gramas (demais pares).
Ver a decisão completa, com os números do experimento e a comparação por
tipo de relação, em [docs/relacoes.md](../../docs/relacoes.md). Este README
é sobre como rodar o código; aquele documento é sobre por que a decisão foi
essa.

## Como rodar

Esta Etapa depende das menções tipadas da Etapa 2 (Caio, `project2/src/entidades/`)
e das arestas do Projeto 1 (`project1/data/processed/`), já disponíveis em `main`.

```bash
pip3 install pandas scikit-learn
pip3 install --break-system-packages -r project2/src/entidades/requirements.txt
python3 -c "import nltk; nltk.download('punkt_tab')"

# 1. Gera as mencoes tipadas (Etapa 2) - prerequisito, gitignored
python3 project2/src/entidades/entidades.py mock

# 2. Gera os pares de relacao (Etapa 4) a partir das mencoes acima
python3 -m project2.src.relacoes.mock.gerar

# 3. Treina, compara e gera as predicoes finais
python3 -m project2.src.relacoes.relacoes
```

Gera `project2/data/relacoes.csv` (predições no split de teste) e
`project2/data/resultados/relacoes.csv` (comparação das 4 combinações
LogisticRegression/LinearSVC × unigrama/1-3-grama em `val`, mais 1 linha
com a config vencedora avaliada em `test`).

## Arquitetura

1. **Regra de paciente** (`apply_patient_rule`): qualquer par onde um dos
   tipos é `Patient` é resolvido por tabela fixa
   (`Symptom→HAS_SYMPTOM`, `Exam→UNDERWENT_EXAM`, `Diagnosis→DIAGNOSED_WITH`,
   `Outcome→HAS_OUTCOME`, `Medication/Treatment→TREATED_WITH`,
   `History→HAS_HISTORY`, `Finding→HAS_FINDING`). Confiança = 1.0.
2. **Classificador de N-gramas**: para os demais pares (`REVEALS`,
   `LOCATED_IN`, `HAS_RESULT`, `SUPPORTS`, `NONE`), um `Pipeline` do
   scikit-learn combina TF-IDF de `between_text`, one-hot dos tipos,
   `distance_chars` e a ordem textual (`source_before_target`, recuperada
   via join com `project2/data/mock/relacoes/entidades.csv`, já que
   `distance_chars` e `between_text` são simétricos e não preservam
   direção).
3. O modelo de produção é **sempre LogisticRegression** (fornece
   `predict_proba` nativo para a coluna `confidence`). `LinearSVC` só
   entra na tabela comparativa, nunca gera a saída final.

## Avaliação contra o gabarito manual

`evaluate_against_gold(df_pred, case_ids, gold_dir)` reusa
`project2/src/montagem/evaluation/metrics.py:evaluate_relations`. Os 2 casos
atribuídos a João (`PMC4630775_01`, `PMC6083636_03`) ainda não foram
anotados manualmente — essa função já está pronta para ser usada assim
que os CSVs em `project2/data/gold/cases/<case_id>/<case_id>-relations.csv`
forem preenchidos.

## Limitações conhecidas

Detalhadas, com números e evidência, em
[docs/relacoes.md](../../docs/relacoes.md#limitações-conhecidas):

- `polarity`/`certainty` são herdados dos atributos das arestas do Projeto 1
  (a Etapa 3 ainda não publicou saída própria).
- A perda de cobertura real (`arestas_descartadas + pares_colapsados`) é
  maior do que `arestas_descartadas` isolado sugere (~28,6% vs ~9%).
- A comparação regra-vs-classificador não é direta: a regra nunca vê um
  `Patient` negativo, o classificador vê ~90% `NONE`.
- A classe `SUPPORTS` tem suporte zero em `val`, tornando a seleção de
  configuração estatisticamente frágil.
- Nenhum teste automatizado cruza a fronteira `mock/gerar.py` → `relacoes.py`.
- Os 2 casos-gabarito de João ainda não foram anotados à mão.
