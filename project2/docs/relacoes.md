# Etapa 4 — decisões de projeto

Código e comandos em [`src/relacoes/`](../src/relacoes/README.md). Os resultados estão na seção
Resultados do [README do projeto](../README.md#resultados).

## Regra para o paciente, classificador para o resto

Quando uma das pontas é o `Patient`, o tipo da outra menção já determina a relação
(`Symptom → HAS_SYMPTOM`, `Exam → UNDERWENT_EXAM` etc., em `PATIENT_RELATION_MAP`). Só as relações
entre duas menções (`HAS_RESULT`, `REVEALS`, `LOCATED_IN`, `SUPPORTS`, `TREATED_WITH`) dependem do
texto. Essas ficam com o classificador de N-gramas.

As duas partes são medidas em separado. A regra nunca vê um par negativo, enquanto ~90% dos pares
do classificador são `NONE`. Um número único que misturasse as duas partes não compararia os métodos.

## Pares de treino resolvidos por offset

A primeira versão do gerador de pares casava o texto da menção com o `label` dos nós do P1. Como
esse rótulo muitas vezes é reescrito, 38% dos casos de treino ficavam sem nenhuma relação positiva.
O [`mock/gerar.py`](../src/relacoes/mock/gerar.py) usa os `char_start`/`char_end` da evidência que o
`edges.csv` do P1 já exporta e resolve cada aresta para a menção do tipo certo que se sobrepõe a
esse trecho. Nenhum casamento por texto sobrou. A perda caiu para 28,9% das arestas, a maior parte
por deduplicação de arestas que apontam para o mesmo par de menções.

## `LogisticRegression` em vez de `LinearSVC`

O `LinearSVC` tem macro-F1 maior na validação silver. Mas a saída precisa de `confianca` em toda
aresta, e só a `LogisticRegression` fornece `predict_proba`. Calibrar o SVC com
`CalibratedClassifierCV(cv=5)` falha, porque `SUPPORTS` tem menos de 5 exemplos no treino.
Nenhum dos dois modelos teve a calibração das probabilidades medida.

## Limitações

- `SUPPORTS` é raro no corpus e tem 1 exemplo no gabarito, então o F1 dessa classe não é conclusivo.
- `class_weight="balanced"` com ~90% de `NONE` favorece recall sobre precisão nas classes raras.
- Relações reflexivas são descartadas, o que afeta só `REVISES` (1 ocorrência).
- `avaliar_gabarito.py` corrige à mão os tipos de 2 casos (`TYPE_OVERRIDE`). Um caso novo precisa
  de entradas próprias.
