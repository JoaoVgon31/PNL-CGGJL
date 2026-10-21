# Guia de anotação do gabarito

Critérios usados para anotar os 8 casos de [`data/gold/`](../data/gold/README.md).

## Fronteiras das menções

1. Sem determinantes no início: `the stomach` → `stomach`.
2. Medidas ficam de fora, porque a montagem as guarda no atributo `size`: `a 6cm cystic lesion` → `cystic lesion`.
3. Sem pontuação nas bordas: `hypokalemic (1` → `hypokalemic`.
4. Modificadores necessários ao sentido ficam: `extensive colitis`, `contrast enhanced computed tomography`, `acute appendicitis`.
5. O texto anotado é exatamente `case_text[start:end]`.

## Tipos

| Tipo | Descrição | Exemplos |
|---|---|---|
| `Symptom` | Sintoma relatado pelo paciente | *weakness*, *abdominal pain*, *fever* |
| `History` | Histórico pessoal ou familiar | *hypertension*, *family history of cancer* |
| `Exam` | Exame laboratorial, de imagem ou procedimento diagnóstico | *computed tomography*, *colonoscopy*, *biopsy* |
| `ExamResult` | Valor numérico ou qualitativo de um exame | *12,476.5 ng/ml*, *positive*, *elevated* |
| `Finding` | Achado objetivo do exame ou da clínica | *cystic lesion*, *erythema*, *mass* |
| `Diagnosis` | Doença ou síndrome diagnosticada | *appendicitis*, *adenocarcinoma*, *COVID-19* |
| `Medication` | Fármaco | *potassium chloride*, *amoxicillin*, *insulin* |
| `Treatment` | Tratamento não medicamentoso ou cirurgia | *appendectomy*, *drainage*, *hemodialysis* |
| `Outcome` | Desfecho ou evolução | *discharged*, *recovery*, *death* |
| `AnatomicalSite` | Estrutura anatômica | *stomach*, *pancreas*, *right lung* |

`Patient` e `Concept` são criados na montagem e não são anotados.

## Polaridade

- `present`: o padrão.
- `absent`: a menção é negada no texto (*"no fever"*, *"denied chest pain"*, *"without malignancy"*).

## Relações

Do paciente (`origem = P1`): `HAS_SYMPTOM`, `UNDERWENT_EXAM`, `DIAGNOSED_WITH`, `TREATED_WITH`,
`HAS_OUTCOME`, `HAS_HISTORY`, `HAS_FINDING`.

Entre menções:

| Relação | Pontas | Exemplo |
|---|---|---|
| `REVEALS` | `Exam` → `Finding` / `ExamResult` | *CT scan* → *cystic lesion* |
| `HAS_RESULT` | `Exam` → `ExamResult` | *potassium level* → *2.1 mEq/L* |
| `SUPPORTS` | `Finding` / `Exam` → `Diagnosis` | *biopsy* → *adenocarcinoma* |
| `LOCATED_IN` | `Finding` / `Symptom` / `ExamResult` → `AnatomicalSite` | *cystic lesion* → *pancreas* |
| `TREATED_WITH` | `Diagnosis` → `Treatment` / `Medication` | *hypertension* → *enalapril* |

## Formato

- `data/gold/mencoes.csv`: `case_id,id,start,end,texto,tipo,mesh,polaridade`
- `data/gold/relacoes.csv`: `case_id,origem,destino,relacao`
