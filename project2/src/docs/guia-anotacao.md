# Guia Rápido de Anotação Manual do Gabarito Ouro (Gold Standard)

**Projeto 2 · Processamento de Linguagem Natural (MC896 / 2026.2)**  
Este guia estabelece os critérios padronizados de anotação manual para os casos clínicos de teste do **Projeto 2**. Todas as estações utilizam este gabarito como verdade fundamental (*Ground Truth*).

---

## 1. Regras de Fronteira das Menções (*Boundaries*)

1. **Sem determinantes iniciais:**  
   *  `the stomach` $\rightarrow$ Anotar apenas `stomach`.
   *  `a 6cm cystic lesion` $\rightarrow$ Anotar `cystic lesion` (medidas vão para atributos na montagem).
2. **Sem pontuação nas bordas:**  
   * Nunca inclua vírgulas, pontos finais ou parênteses no span (`hypokalemic (1` $\rightarrow$ `hypokalemic`).
3. **Modificadores clínicos essenciais:**  
   * Mantenha adjetivos anatômicos ou de severidade indispensáveis para a semântica (`extensive colitis`, `contrast enhanced computed tomography`, `acute appendicitis`).
4. **Alinhamento estrito:**  
   * O texto anotado deve bater **caractere por caractere** com o texto original:  
     `case_text[char_start:char_end] == texto`.

---

## 2. Tipos de Entidades Clínicas (10 Classes)

| Tipo | Descrição | Exemplo da Amostra |
|---|---|---|
| **`Symptom`** | Sintoma subjetivo relatado pelo paciente | *weakness*, *abdominal pain*, *fever* |
| **`History`** | Histórico prévio pessoal ou familiar | *hypertension*, *family history of cancer* |
| **`Exam`** | Procedimento diagnóstico, exame laboratorial ou de imagem | *computed tomography*, *colonoscopy*, *biopsy* |
| **`ExamResult`** | Valor numérico ou qualitativo de um exame | *12,476.5 ng/ml*, *positive*, *elevated* |
| **`Finding`** | Achado objetivo observado ou detectado no exame/clínica | *cystic lesion*, *erythema*, *mass* |
| **`Diagnosis`** | Doença, patologia ou síndrome diagnosticada | *appendicitis*, *adenocarcinoma*, *COVID-19* |
| **`Medication`** | Fármaco ou princípio ativo administrado | *potassium chloride*, *amoxicillin*, *insulin* |
| **`Treatment`** | Procedimento terapêutico não medicamentoso / cirurgia | *appendectomy*, *drainage*, *hemodialysis* |
| **`Outcome`** | Desfecho clínico ou evolução do quadro | *discharged*, *recovery*, *death* |
| **`AnatomicalSite`**| Estrutura anatômica ou órgão afetado | *stomach*, *pancreas*, *right lung* |

> [!NOTE]
> `Patient` (metadados do paciente) e `Concept` (códigos MeSH) são instanciados na montagem do grafo e **não** devem ser anotados como menções de texto.

---

## 3. Atributos: Polaridade e Certeza

Toda anotação clínica carrega dois modificadores obrigatórios:
* **Polaridade (`polarity`):**
  * `present` (padrão): A entidade/achado foi constatada no paciente.
  * `absent`: A entidade foi expressamente negada no texto (*"no fever"*, *"denied chest pain"*, *"without malignancy"*).
* **Certeza (`certainty`):**
  * `asserted` (padrão): Fato confirmado pelo médico.
  * `hypothetical`: Suspeita, hipótese ou diagnóstico diferencial (*"suggesting appendicitis"*, *"possible lesion"*).

---

## 4. Tipos de Relações Clínicas

As relações ligam entidades pelo seu identificador (`source` $\rightarrow$ `target`):

| Relação | Sentido Semântico | Exemplo |
|---|---|---|
| **`REVEALS`** | `Exam` $\rightarrow$ `Finding` / `ExamResult` | *CT scan* $\rightarrow$ *cystic lesion* |
| **`HAS_RESULT`** | `Exam` $\rightarrow$ `ExamResult` | *potassium level* $\rightarrow$ *2.1 mEq/L* |
| **`SUPPORTS`** | `Finding`/`Exam` $\rightarrow$ `Diagnosis` | *biopsy* $\rightarrow$ *adenocarcinoma* |
| **`LOCATED_IN`**| `Finding`/`Symptom` $\rightarrow$ `AnatomicalSite` | *cystic lesion* $\rightarrow$ *pancreas* |
| **`TREATED_WITH`**| `Diagnosis` $\rightarrow$ `Treatment`/`Medication`| *hypertension* $\rightarrow$ *enalapril* |

---

## 5. Formato dos Arquivos de Entrega

Para cada caso em `project2/data/gold/cases/<case_id>/`:
1. `<case_id>-entities.csv`:
   ```csv
   case_id,ent_id,char_start,char_end,texto,type,concept_code,polarity,certainty
   ```
2. `<case_id>-relations.csv`:
   ```csv
   case_id,rel_id,source,target,relation,polarity,certainty
   ```
Valide seus arquivos executando o consolidador oficial:
```bash
python -m project2.src.data.gold_manager
```
