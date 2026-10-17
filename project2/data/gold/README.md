# Gabarito Ouro (Gold Standard) · Anotacao Manual

Este diretorio contem as diretrizes e arquivos do **Gabarito Ouro (Gold Standard)** do Projeto 2.

Conforme a **Regra 3** do planejamento ([divisao-do-trabalho.md](../docs/divisao-do-trabalho.md)):
> **Gabarito feito por todos.** Cada pessoa anota a mao 1 ou 2 casos (8 a 10 no total), para medir acerto e nao so volume.

Os casos selecionados para anotacao pertencem estritamente ao conjunto de **teste** (e validacao) definido em `project2/data/splits.json`, garantindo avaliacao justa sem contaminacao dos conjuntos de treino.

---

## 1. Casos Distribuidos para Anotacao

| Integrante | Caso 1 (Obrigatorio) | Caso 2 (Opcional/Extra) | Split |
|---|---|---|---|
| **Gabriel** | `PMC11259348_01` | `PMC7086412_01` | Teste / Val |
| **Caio** | `PMC11723754_01` | `PMC7102447_01` | Teste / Val |
| **Lucas** | `PMC3437073_01` | — | Teste |
| **João** | `PMC4630775_01` | `PMC6083636_03` | Teste |
| **George** | `PMC9532611_01` | `PMC9969157_01` | Teste |

---

## 2. Formato das Tabelas de Anotacao

Cada integrante deve preencher dois arquivos CSV para cada caso anotado:
1. `<case_id>-gold-entities.csv`
2. `<case_id>-gold-relations.csv`

### Esquema: `<case_id>-gold-entities.csv`

```csv
case_id,ent_id,char_start,char_end,texto,type,concept_code
PMC11259348_01,t1,24,42,computed tomography,Exam,D014057
PMC11259348_01,t2,55,68,cystic lesion,Finding,
PMC11259348_01,t3,80,87,pancreas,AnatomicalSite,ANAT002
```

- `case_id`: Identificador do caso.
- `ent_id`: Identificador unico da entidade no caso (`t1`, `t2`, etc.).
- `char_start` e `char_end`: Offsets de caractere exatos no `case_text`.
- `texto`: Trecho exato correspondente a `case_text[char_start:char_end]`.
- `type`: Tipo clinico (`Exam`, `Finding`, `Symptom`, `Diagnosis`, `AnatomicalSite`, `Medication`, `Treatment`, `Patient`, `Outcome`).
- `concept_code`: Codigo MeSH correspondente (ex.: `D014057`), ou vazio se nao houver.

### Esquema: `<case_id>-gold-relations.csv`

```csv
case_id,source,target,relation,polarity,certainty
PMC11259348_01,t1,t2,REVEALS,present,asserted
PMC11259348_01,t2,t3,LOCATED_IN,present,asserted
```

- `source` e `target`: `ent_id` correspondente da tabela de entidades.
- `relation`: Relacao clinica (`REVEALS`, `LOCATED_IN`, `HAS_SYMPTOM`, `UNDERWENT_EXAM`, `DIAGNOSED_WITH`, `TREATED_WITH`, `HAS_FINDING`, etc.).
- `polarity`: `present` (achado afirmado) ou `absent` (achado negado/ausente).
- `certainty`: `asserted` (afirmado/confirmado), `hedged` (hipotese/suspeita) ou `conditional`.

---

## 3. Pre-anotacao Auxiliar (Mock)

Para acelerar a anotacao, as predicoes preliminares do Projeto 1 para esses casos ja estao disponiveis em `project2/data/silver/`. Voce pode usalas como ponto de partida e apenas auditar, corrigir fronteiras, ajustar tipos e incluir arestas faltantes.
