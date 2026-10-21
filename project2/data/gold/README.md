# Gabarito Manual (Gold Standard) — Projeto 2

Este diretório contém o **gabarito padrão-ouro (*Gold Standard*)** do Projeto 2, concebido e curado manualmente pelos integrantes do grupo na **Issue [#29](https://github.com/caiomelloni/PNL-CGGJL/issues/29)**.

O gabarito serve como base para a avaliação cega de desempenho das etapas de aprendizado de máquina e regras clássicas (Etapas 2, 3, 4 e 5).
---
## 1. Casos Anotados

Foram selecionados e anotados manualmente **8 casos clínicos** da amostra MultiCaRe, cobrindo diferentes graus de complexidade e extensões textuais:

| Case ID | Arquivo de Texto | Entidades | Relações |
|---|---|---:|---:|
| `PMC11259348_01` | [`cases/PMC11259348_01/case_text.txt`](cases/PMC11259348_01/case_text.txt) | 16 | 15 |
| `PMC11723754_01` | [`cases/PMC11723754_01/case_text.txt`](cases/PMC11723754_01/case_text.txt) | 32 | 28 |
| `PMC3437073_01` | [`cases/PMC3437073_01/case_text.txt`](cases/PMC3437073_01/case_text.txt) | 52 | 40 |
| `PMC4630775_01` | [`cases/PMC4630775_01/case_text.txt`](cases/PMC4630775_01/case_text.txt) | 9 | 8 |
| `PMC6083636_03` | [`cases/PMC6083636_03/case_text.txt`](cases/PMC6083636_03/case_text.txt) | 20 | 19 |
| `PMC6949661_01` | [`cases/PMC6949661_01/case_text.txt`](cases/PMC6949661_01/case_text.txt) | 58 | 51 |
| `PMC9532611_01` | [`cases/PMC9532611_01/case_text.txt`](cases/PMC9532611_01/case_text.txt) | 15 | 13 |
| `PMC9969157_01` | [`cases/PMC9969157_01/case_text.txt`](cases/PMC9969157_01/case_text.txt) | 22 | 19 |
| **Total Consolidado** | — | **224** | **193** |

A lista com os identificadores dos 8 casos está salva em [`casos.txt`](casos.txt).

---

## 2. Estrutura de Arquivos

```text
data/gold/
├── casos.txt                         <- Lista com os IDs dos 8 casos de teste
├── manifest.json                     <- Manifesto de validação e auditoria dos casos
├── mencoes.csv                       <- Tabela consolidada com as 224 menções anotadas
├── relacoes.csv                      <- Tabela consolidada com as 193 relações anotadas
├── gold_entidades.csv                <- Cópia canônica das entidades para os módulos de avaliação
├── gold_relacoes.csv                 <- Cópia canônica das relações para os módulos de avaliação
├── template_gold_entities.csv        <- Gabarito template de cabeçalho para entidades
├── template_gold_relations.csv       <- Gabarito template de cabeçalho para relações
└── cases/                            <- Anotações individuais por caso
    ├── PMC11259348_01/
    │   ├── case_text.txt             <- Texto exato do caso clínico
    │   ├── PMC11259348_01-entities.csv
    │   └── PMC11259348_01-relations.csv
    └── ...
```

---

## 3. Esquema e Taxonomia das Anotações

### 3.1 Entidades / Menções ([`mencoes.csv`](mencoes.csv))
- `case_id`: Identificador do caso clínico.
- `id`: Identificador da menção no caso (ex: `g1`, `g2`).
- `start`: Posição inicial do caractere no `case_text` (*0-indexed*).
- `end`: Posição final do caractere (*exclusivo*).
- `texto`: Trecho de texto exato delimitado por `[start:end]`.
- `tipo`: Categoria semântica da taxonomia:
  - `Exam`, `ExamResult`, `Finding`, `Symptom`, `Diagnosis`, `Treatment`, `Medication`, `Outcome`, `AnatomicalSite`, `History`.
- `mesh`: Código no vocabulário controlado MeSH (ex: `D005334`), quando aplicável.
- `polaridade`:
  - `present`: Achado/sintoma/diagnóstico confirmado.
  - `absent`: Achado expressamente negado ou descartado no texto.

### 3.2 Relações ([`relacoes.csv`](relacoes.csv))
- `case_id`: Identificador do caso clínico.
- `origem`: ID da entidade de origem (`P1` para o paciente ou `gX` para menções).
- `destino`: ID da entidade de destino (`gY`).
- `relacao`: Tipo da relação clínica:
  - **Relações de Paciente:** `HAS_SYMPTOM`, `UNDERWENT_EXAM`, `DIAGNOSED_WITH`, `TREATED_WITH`, `HAS_OUTCOME`, `HAS_HISTORY`, `HAS_FINDING`.
  - **Relações entre Menções:** `HAS_RESULT`, `REVEALS`, `LOCATED_IN`, `SUPPORTS`.

---

## 4. Auditoria e Validação

A consistência dos limites de caracteres, spans de texto e integridade referencial foi verificada via script automatizado com resultado consolidado em [`manifest.json`](manifest.json):
1. **Validação de Spans:** Nenhum caractere `start` ou `end` diverge do `case_text.txt`.
2. **Consistência de IDs:** Toda relação aponta para nós de origem e destino declarados no próprio caso.
