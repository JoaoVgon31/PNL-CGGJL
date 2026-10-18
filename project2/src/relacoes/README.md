# Etapa 4 — Relações entre entidades (Issue #35)

Infere relações clínicas entre entidades combinando uma regra fixa (pares
envolvendo o paciente) com um classificador de N-gramas (demais pares).

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
`project2/src/evaluation/metrics.py:evaluate_relations`. Os 2 casos
atribuídos a João (`PMC4630775_01`, `PMC6083636_03`) ainda não foram
anotados manualmente — essa função já está pronta para ser usada assim
que os CSVs em `project2/data/gold/cases/<case_id>/<case_id>-relations.csv`
forem preenchidos.

## Limitações conhecidas

- `polarity`/`certainty` na saída final são herdados dos atributos já
  presentes nas arestas do Projeto 1 (repassados por
  `project2/src/relacoes/mock/gerar.py`), já que a Etapa 3 (tipos/polaridade)
  ainda não tem saída própria. Revisitar quando a Etapa 3 estiver pronta.
- Os dados de treino/val/teste são gerados por `project2/src/relacoes/mock/gerar.py`,
  que resolve as relações do Projeto 1 contra as menções tipadas da Etapa 2 (Caio)
  via sobreposição de offset de caractere — nunca por casamento de texto (ver
  `docs/superpowers/specs/2026-10-18-relacoes-mock-main-design.md` para o porquê).
  Algumas arestas do Projeto 1 são descartadas quando nenhuma menção do tipo certo
  cai na janela de evidência (`arestas_descartadas` no retorno de `gerar()`); isso
  é intencional — perder um exemplo é melhor que criar um casamento errado.
  Além disso, `resolver_positivos` deduplica pares `(origem_id, destino_id)`
  repetidos entre arestas diferentes, contados separadamente em
  `pares_colapsados`: ao contrário de `arestas_descartadas` (nenhuma menção
  candidata encontrada), um par colapsado sempre tem a mesma relação do par já
  resolvido, então não gera rótulo errado — só reduz a contagem bruta de
  arestas. Nos dados reais, a perda de cobertura total é `arestas_descartadas +
  pares_colapsados`, cerca de 28,6% das arestas elegíveis, bem maior que os
  ~9% que `arestas_descartadas` sozinho sugere; some os dois contadores ao
  avaliar quanto do Projeto 1 efetivamente chega aos CSVs de saída.
- **Comparação regra-vs-ML estruturalmente injusta para `Patient`**: nos dados
  reais, todos os pares envolvendo `Patient` são positivos (nenhum `NONE`
  gerado para esse tipo), então a regra de `relacoes.py` "acerta 100%" só
  porque o gerador nunca cria um exemplo negativo envolvendo `Patient` para
  ela errar. O classificador de N-gramas, por outro lado, recebe uma fatia
  com ~90% `NONE`. Uma conclusão de relatório do tipo "a regra supera o
  classificador" estaria medindo uma assimetria do gerador de dados, não uma
  diferença real entre os dois métodos.
- **Baixo suporte da classe `SUPPORTS`**: nos dados reais, a classe `SUPPORTS`
  tem suporte 0 tanto em `val` quanto em `test`, então a seleção entre a
  configuração unigrama e 1-3-grama (`select_best_lr_config`) acaba decidida
  só pelas poucas classes com suporte real nesses splits. Isso torna a
  escolha de configuração — e qualquer métrica agregada que dependa dela —
  estatisticamente frágil; vale mencionar essa limitação antes de tirar
  conclusões fortes dos números no relatório comparativo.
