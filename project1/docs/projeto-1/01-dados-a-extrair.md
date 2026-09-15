# 01 — Quais dados extrair dos casos clínicos

> Entregável da [issue #1](https://github.com/caiomelloni/PNL-CGGJL/issues/1) — Projeto 1 (MC896, 2026).
> Define **o que** extrair do `case_text`. O **como representar** é a issue [#2](https://github.com/caiomelloni/PNL-CGGJL/issues/2); o **como extrair**, as issues [#3](https://github.com/caiomelloni/PNL-CGGJL/issues/3)–[#6](https://github.com/caiomelloni/PNL-CGGJL/issues/6). (outros métodos de extração podem ser adicionados além das issues 3-6)

**Amostra:** 56 casos em `sample/cases.csv`, de 50 artigos em `sample/metadata.csv`. Os percentuais abaixo foram medidos sobre esses 56 casos e indicam em quantos há pista lexical da categoria.


**Regra geral:** só extraímos o que é um trecho identificável do texto. Nada é inferido por conhecimento clínico nosso.

**Como ler os domínios de valor.** Valores em `code` são **vocabulário fechado**: a extração mapeia para um deles ou deixa `null`. "Texto normalizado" é string aberta, sujeita às regras de [#4](https://github.com/caiomelloni/PNL-CGGJL/issues/4). Todo atributo aceita `null` quando o texto não informa — só `label` e as chaves de `Patient` são obrigatórios.

---

## 1. Entidades

| # | Entidade | % casos |
|---|---|---:|
| 1 | `Patient` | 100% |
| 2 | `Symptom` | 84% |
| 3 | `Finding` | 89% |
| 4 | `History` | 48% |
| 5 | `Exam` | 91% |
| 6 | `ExamResult` | 66% |
| 7 | `Diagnosis` | 91% |
| 8 | `Medication` | 62% |
| 9 | `Treatment` | 84% |
| 10 | `AnatomicalSite` | 84% |
| 11 | `Outcome` | 73% |

---

### 1.1 `Patient`

**Por quê.** É a âncora do grafo: toda entidade clínica pendura nele, direta ou indiretamente. Sem ele o caso vira uma lista solta de termos. Um nó por `case_id`.

**Exemplo — PMC5137649_01:** *"A 44-year-old woman presented with..."*

| Atributo | Descrição | Valores possíveis |
|---|---|---|
| `case_id` | Identificador do caso; chave primária vinda do CSV | String no padrão `PMC<dígitos>_<NN>` — ex. `PMC5137649_01` |
| `article_id` | PMCID do artigo de origem; liga a `metadata.csv` | String `PMC<dígitos>` — ex. `PMC5137649` |
| `age` | Idade numérica do paciente | Decimal ≥ 0, ou `null` (5 dos 56 casos) |
| `age_unit` | Unidade da idade — necessária porque a amostra tem recém-nascidos | `years` \| `months` \| `days` \| `weeks_gestational` |
| `gender` | Sexo, conforme o domínio do CSV | `Female` \| `Male` \| `Transgender` \| `Unknown` — na amostra: 30 / 22 / 0 / 4 |

> ⚠️ As colunas `age`/`gender` do CSV **não são confiáveis**: 8 dos 56 casos têm anomalia. Em PMC9969157_01 o CSV diz `age=7.0`, mas o texto é *"born at 33 **2/7** weeks gestational age to a **36-year-old** mother"* — o 7 veio do denominador da fração. Preferir a idade extraída do texto quando as duas divergirem.

---

### 1.2 `Symptom`

**Por quê.** É a queixa que motiva o caso e a principal evidência que sustenta o diagnóstico. Gatilhos: `presented with`, `complained of`, `a N-day history of`.

**Exemplo — PMC5137649_01:** *"presented with a 3-day history of right flank and lower quadrant abdominal pain associated with nausea and constipation"* → três sintomas.

| Atributo | Descrição | Valores possíveis |
|---|---|---|
| `label` | Forma normalizada do sintoma | Texto normalizado — `abdominal pain`, `nausea`, `constipation` |
| `polarity` | Se o sintoma é afirmado ou negado no texto | `present` \| `absent` |
| `duration` | Há quanto tempo o sintoma dura | Número + unidade de tempo — `3 days`, `one year` |
| `onset` | Quando ou como começou | `sudden` \| `gradual` \| expressão temporal livre |
| `course` | Como evoluiu | `progressive` \| `intermittent` \| `stable` \| `worsening` \| `improving` |
| `severity` | Intensidade, quando declarada | `mild` \| `moderate` \| `severe` \| `low-grade` |

> `polarity` é obrigatório: sintoma negado (*"no fever, night sweating, or weight loss"*, PMC3859158_01) é informação, não ausência de dado — vira `polarity=absent`, nunca é descartado.

---

### 1.3 `Finding`

**Por quê.** É o que o clínico ou o exame **observa**, distinto do que o paciente relata. Aparece em 89% dos casos e é o elo entre exame e diagnóstico.

**Exemplo — PMC5137649_01:** *"demonstrating a 6cm cystic lesion between the stomach and body/tail of the pancreas"* → `source=imaging`, `size=6 cm`.

| Atributo | Descrição | Valores possíveis |
|---|---|---|
| `label` | Forma normalizada do achado | Texto normalizado — `cystic lesion`, `epigastric tenderness` |
| `source` | Que tipo de avaliação produziu o achado | `physical_exam` \| `imaging` \| `pathology` \| `lab` \| `endoscopy` \| `surgical` |
| `polarity` | Se foi observado ou explicitamente excluído | `present` \| `absent` |
| `certainty` | Grau de asserção do texto | `confirmed` \| `probable` \| `suspected` |
| `size` | Dimensão medida, uma ou mais | Número + unidade — `6 cm`; multidimensional `9.5 x 4.5 x 2.0 cm` |

> Achado **excluído** é a razão de `polarity` existir aqui. Em PMC5137649_01, *"FNA of the cyst demonstrated **no evidence of** malignancy"* — sem tratar a negação, o extrator produz um diagnóstico de malignidade que o texto nega.

---

### 1.4 `History`

**Por quê.** Separa o que o paciente **já tinha** do que foi diagnosticado **neste** episódio. Sem essa distinção, comorbidade prévia e diagnóstico atual viram a mesma coisa e o grafo perde o eixo temporal.

**Exemplo — PMC7102447_01:** *"a past medical history significant for hypertension, asthma, and minimally invasive bioprosthetic mitral valve replacement"* → três nós.

| Atributo | Descrição | Valores possíveis |
|---|---|---|
| `label` | Condição, cirurgia ou exposição prévia | Texto normalizado — `hypertension`, `asthma` |
| `subject` | De quem é o histórico | `patient` \| `family` |
| `polarity` | Se o histórico é afirmado ou negado | `present` \| `absent` |
| `relation_degree` | Parentesco, quando `subject=family` | `mother` \| `father` \| `sibling` \| `unspecified` |
| `category` | Natureza do antecedente | `condition` \| `surgery` \| `exposure` \| `medication` |

> Cuidado com o gatilho: em *"a 3-day **history of** abdominal pain"* (PMC5137649_01), `history of` marca duração de sintoma atual, não condição prévia. A regra precisa exigir que não venha precedido de expressão de duração.

---

### 1.5 `Exam`

**Por quê.** É o procedimento diagnóstico que **produz** resultados e achados — o nó intermediário sem o qual não dá para dizer de onde veio cada evidência.

**Exemplo — PMC5137649_01:** *"She underwent contrast enhanced computed tomography"* → `modality=imaging`.

| Atributo | Descrição | Valores possíveis |
|---|---|---|
| `label` | Nome normalizado do exame | Texto normalizado — `computed tomography`, `carcinoembryonic antigen` |
| `modality` | Tipo de exame | `laboratory` \| `imaging` \| `endoscopy` \| `pathology` \| `functional` |
| `timing` | Momento em que foi realizado | `on admission` \| `initial` \| `follow-up` \| expressão temporal livre |
| `abbreviation` | Sigla definida no próprio caso | String em maiúsculas — `CT`, `EUS`, `CEA` |
| `contrast` | Se usou contraste (só para imagem) | `true` \| `false` |

> 70% dos casos definem siglas entre parênteses (*"carcinoembryonic antigen (CEA)"*). É preciso casar sigla e expansão **dentro do mesmo caso** e unificar as menções.

---

### 1.6 `ExamResult`

**Por quê.** É a medida quantitativa que o enunciado pede nominalmente ("valores associados a resultados de exames [...] bem como suas unidades de medida"). Separado de `Finding` porque a extração é outra: regex de valor+unidade, não casamento com léxico.

**Exemplo — PMC10106591_01:** *"normal troponin I of 0.016 ng/mL (normal range, 0-0.04 ng/mL)"* → `value=0.016`, `unit=ng/mL`, faixa `0`–`0.04`, `interpretation=normal`.

| Atributo | Descrição | Valores possíveis |
|---|---|---|
| `value` | Valor medido | Decimal (`0.016`, `12476.5`), ou categórico `positive` \| `negative` |
| `unit` | Unidade normalizada (UCUM) | `ng/mL` \| `U/L` \| `mg/dL` \| `g/dL` \| `mmol/L` \| `mm/h` \| `%` \| `/µL` \| … \| `null` |
| `reference_range_low` | Limite inferior da faixa normal | Decimal, ou `null` em faixa aberta inferiormente |
| `reference_range_high` | Limite superior da faixa normal | Decimal, ou `null` em faixa aberta superiormente |
| `reference_range_raw` | Texto original da faixa, para auditoria | String — `normal range, 0-0.04 ng/mL`; `normal range <20` |
| `interpretation` | Leitura do resultado | `normal` \| `elevated` \| `decreased` \| `abnormal` \| `positive` \| `negative` |
| `interpretation_source` | Como a interpretação foi obtida | `stated` (declarada no texto) \| `derived` (calculada da faixa) \| `null` |
| `raw_text` | Trecho original do valor, antes de normalizar | String — `12,476.5ng/ml` |

> Ver §3 para as regras de valor, unidade e faixa.

---

### 1.7 `Diagnosis`

**Por quê.** É a conclusão do caso — o nó para onde converge a evidência. Gatilhos: `was diagnosed with`, `a diagnosis of`, `consistent with`, `final pathology revealed`.

**Exemplo — PMC11259348_01:** *"was diagnosed with PCH after having positive Donath-Landsteiner test"* → `certainty=confirmed`.

| Atributo | Descrição | Valores possíveis |
|---|---|---|
| `label` | Nome normalizado do diagnóstico | Texto normalizado — `paroxysmal cold hemoglobinuria`, `gastric duplication cyst` |
| `certainty` | Grau de confirmação expresso no texto | `confirmed` \| `probable` \| `suspected` \| `excluded` |
| `polarity` | Se o diagnóstico é afirmado ou descartado | `present` \| `absent` |
| `role` | Papel no caso | `principal` \| `secondary` \| `differential` |
| `basis` | Sobre o que a conclusão se apoia, quando o texto diz | Texto livre — `Donath-Landsteiner test`, `final pathology` |

> `certainty` importa porque 61% dos casos usam hedging. Em PMC5137649_01 o texto diz *"**suggesting** the diagnosis of a mucinous pancreatic cystic neoplasm"* e só depois *"Final pathology revealed [...] **consistent with** a GDC"* — tratar os dois como afirmação equivalente apagaria o raciocínio clínico.

---

### 1.8 `Medication`

**Por quê.** O enunciado pede dosagens e unidades. Aparece em 62% dos casos com dose explícita.

**Exemplo — PMC7718649_01:** *"oseltamivir 75 mg twice daily, arbidol 0.3 g twice daily, moxifloxacin 0.4 g once daily"* → três medicamentos, `route=oral` herdado do escopo da frase.

| Atributo | Descrição | Valores possíveis |
|---|---|---|
| `label` | Nome do fármaco, normalizado | Texto normalizado — `oseltamivir`, `prednisone` |
| `dose_value` | Quantidade administrada por tomada | Decimal — `75`, `0.3`, `1.4` |
| `dose_unit` | Unidade da dose | `mg` \| `g` \| `mcg` \| `IU` \| `mL` \| `units` |
| `frequency` | Quantas vezes por período | `once daily` \| `twice daily` \| `three times daily` \| `four times daily` \| `as needed` \| texto livre |
| `route` | Via de administração | `oral` \| `intravenous` \| `intramuscular` \| `subcutaneous` \| `topical` \| `inhaled` |
| `duration` | Por quanto tempo foi mantido | Número + unidade — `5 days` |
| `dose_change` | Como a dose muda em relação à menção anterior do mesmo fármaco | `initial` \| `increased` \| `reduced` \| `maintained` \| `discontinued` |
| `timing` | Quando começou | Expressão temporal — `since February 4` |

> `dose_change` existe porque a dose muda ao longo do caso: no mesmo PMC7718649_01, prednisona vai de *"increased dose of prednisone (25 mg once daily)"* para *"Dosage of prednisone was reduced to 15 mg once daily"*. Um nó único por fármaco perde a trajetória.

---

### 1.9 `Treatment`

**Por quê.** O enunciado pede "tratamentos", e `Medication` cobre só o farmacológico. Cirurgias e procedimentos aparecem em 84% dos casos.

**Exemplo — PMC5137649_01:** *"A laparoscopic distal pancreatectomy was planned"* e depois *"the procedure was converted to an open resection"*.

| Atributo | Descrição | Valores possíveis |
|---|---|---|
| `label` | Nome normalizado da intervenção | Texto normalizado — `laparoscopic distal pancreatectomy`, `blood transfusion` |
| `type` | Natureza da intervenção | `surgery` \| `procedure` \| `transfusion` \| `supportive` \| `radiotherapy` |
| `status` | Se foi de fato realizada | `planned` \| `performed` \| `converted` \| `refused` |
| `converted_to` | Para o que a conduta mudou, quando `status=converted` | Texto normalizado — `open resection` |
| `timing` | Quando ocorreu | Expressão temporal — `postoperative day 4` |
| `intent` | Finalidade | `curative` \| `palliative` \| `diagnostic` \| `supportive` |

> `status` é necessário porque *"was planned"* não é o mesmo que realizado — e nesse caso o plano de fato **não** se concretizou como planejado.

---

### 1.10 `AnatomicalSite`

**Por quê.** Pedida nominalmente pelo enunciado ("regiões anatômicas"), com 244 ocorrências em 84% dos casos. É o eixo que permite consultar o grafo por órgão em vez de por doença.

**Exemplo — PMC5137649_01:** *"a 6cm cystic lesion between the stomach and body/tail of the pancreas"* → dois sítios, um com `region_qualifier=body/tail`.

| Atributo | Descrição | Valores possíveis |
|---|---|---|
| `label` | Órgão ou região, normalizado | Texto normalizado — `stomach`, `pancreas`, `Sylvian fissure` |
| `laterality` | Lado do corpo | `left` \| `right` \| `bilateral` |
| `region_qualifier` | Porção ou orientação dentro da estrutura | `upper` \| `lower` \| `proximal` \| `distal` \| `anterior` \| `posterior` \| `body/tail` \| texto livre |

> Não geramos sítio quando o órgão já está embutido no nome da doença (*"pancreatitis"* não gera `pancreas`) — duplicaria o que já está em `Diagnosis`.

---

### 1.11 `Outcome`

**Por quê.** Fecha a narrativa: alta, óbito, resolução ou recorrência. Presente em 73% dos casos.

**Exemplo — PMC5137649_01:** *"The patient was discharged home on postoperative day 4"* → `type=discharge`, `length_of_stay=4 days`.

| Atributo | Descrição | Valores possíveis |
|---|---|---|
| `label` | Descrição normalizada do desfecho | Texto normalizado — `discharged home`, `symptom resolution` |
| `type` | Categoria do desfecho | `discharge` \| `death` \| `resolution` \| `recurrence` \| `complication` \| `improvement` |
| `timing` | Quando ocorreu | Expressão temporal — `postoperative day 4`, `2 days after surgery` |
| `length_of_stay` | Duração da internação | Número + unidade — `4 days` |
| `follow_up_duration` | Tempo de seguimento após a alta | Número + unidade — `24 months` |
| `polarity` | Se o desfecho ocorreu ou foi negado | `present` \| `absent` |

> Atenção à adversativa: em PMC2700431_01, *"the patient improved with regard to his infection **but later expired**"* — pegar o primeiro verbo de desfecho erra o desfecho real. E `polarity=absent` cobre *"no evidence of recurrence"* (PMC6354154_01), que é desfecho bom, não dado faltante.

---

## 2. Arestas

| Aresta | Origem → Destino |
|---|---|
| `HAS_SYMPTOM` | Patient → Symptom |
| `HAS_HISTORY` | Patient → History |
| `UNDERWENT_EXAM` | Patient → Exam |
| `HAS_RESULT` | Exam → ExamResult |
| `REVEALS` | Exam \| Treatment → Finding |
| `HAS_FINDING` | Patient → Finding |
| `SUPPORTS` | Symptom \| Finding \| ExamResult \| History → Diagnosis |
| `DIAGNOSED_WITH` | Patient → Diagnosis |
| `TREATED_WITH` | Patient \| Diagnosis → Treatment \| Medication |
| `LOCATED_IN` | Symptom \| Finding \| Treatment → AnatomicalSite |
| `HAS_OUTCOME` | Patient → Outcome |
| `REVISES` | Diagnosis → Diagnosis |

### 2.1 Atributos comuns a toda aresta

Valem para as 12 relações; nenhuma aresta tem atributo próprio.

| Atributo | Descrição | Valores possíveis |
|---|---|---|
| `evidence_text` | Trecho do `case_text` que evidencia a relação | String — `She underwent contrast enhanced computed tomography` |
| `trigger` | Marca lexical que disparou a extração da relação | String do léxico de gatilhos — `presented with`, `underwent`, `after having` |
| `certainty` | Se a relação é afirmada ou apenas sugerida pelo texto | `asserted` \| `hedged` |
| `char_start` / `char_end` | Offsets do trecho no `case_text`, para auditoria | Inteiros ≥ 0 |

> Guardamos **trecho e offsets**: sem alguma ancoragem não há como auditar nem avaliar a extração depois. Ver o esquema do grafo em [02](02-esquema-grafo.md).

### 2.2 Cada aresta

**`HAS_SYMPTOM` · Patient → Symptom**
Liga o paciente à queixa que motivou o atendimento. É a porta de entrada da narrativa.
*PMC5137649_01:* *"A 44-year-old woman **presented with** a 3-day history of right flank [...] abdominal pain"*

**`HAS_HISTORY` · Patient → History**
Separa a condição preexistente do quadro atual, dando ao grafo um antes e um depois.
*PMC7102447_01:* *"A 65-year-old male **with a past medical history significant for** hypertension, asthma..."*

**`UNDERWENT_EXAM` · Patient → Exam**
Registra que a investigação foi feita — inclusive quando não produz achado, o que é informação diagnóstica.
*PMC5137649_01:* *"She **underwent** contrast enhanced computed tomography"*

**`HAS_RESULT` · Exam → ExamResult**
Prende o valor ao exame que o produziu. Sem ela, `12,476.5 ng/ml` é um número sem referente.
*PMC5137649_01:* *"a carcinoembryonic antigen (CEA) **level of** 12,476.5ng/ml"*

**`REVEALS` · Exam | Treatment → Finding**
Registra a **procedência** do achado. A cirurgia entra como origem porque produz achado intraoperatório tanto quanto um exame. O mesmo achado visto por dois exames tem peso diferente de um achado visto por um só.
*PMC5137649_01:* *"contrast enhanced computed tomography, **demonstrating** a 6cm cystic lesion"*

**`HAS_FINDING` · Patient → Finding**
Para achado de exame físico, que não vem de um `Exam` nomeado e por isso liga direto ao paciente.
*PMC3437073_01:* *"**On examination**, a lobulated subcutaneous mass measuring about 7 cm in diameter"*

**`SUPPORTS` · Symptom | Finding | ExamResult | History → Diagnosis**
É a aresta que torna o grafo um grafo de **raciocínio** e não só de fatos: mostra qual evidência sustenta qual conclusão. Só criada com marca textual explícita (`suggesting`, `after having`, `based on`, `consistent with`).
*PMC11259348_01:* *"was diagnosed with PCH **after having** positive Donath-Landsteiner test"*

**`DIAGNOSED_WITH` · Patient → Diagnosis**
Atribui a conclusão ao paciente. Distinta de `SUPPORTS`, que atribui a evidência ao diagnóstico.
*PMC11259348_01:* *"A child admitted with fever [...] **was diagnosed with** PCH"*

**`TREATED_WITH` · Patient | Diagnosis → Treatment | Medication**
Liga a conduta ao caso. Aponta para o diagnóstico quando o texto dá a indicação, e para o paciente quando não dá.
*PMC11259348_01:* *"The patient **was transfused with** group-specific cross-match-compatible blood"*

**`LOCATED_IN` · Symptom | Finding | Treatment → AnatomicalSite**
Permite consultar o grafo por região do corpo, atravessando as categorias clínicas.
*PMC3917415_01:* *"SAH **in** her right Sylvian fissure"*

**`HAS_OUTCOME` · Patient → Outcome**
Fecha o caso com o desfecho.
*PMC5137649_01:* *"The patient **was discharged home on** postoperative day 4"*

**`REVISES` · Diagnosis → Diagnosis**
Registra que um diagnóstico **substituiu** outro. Sem ela, um caso com hipótese revista produz dois diagnósticos concorrentes sem indicar qual prevaleceu.
*PMC5137649_01:* a hipótese *"suggesting the diagnosis of a mucinous pancreatic cystic neoplasm"* é substituída por *"Final pathology revealed [...] consistent with a GDC"*.

---

## 3. Valores, unidades e faixas de referência

1. **Valor e unidade são inseparáveis.** `value` numérico + `unit` normalizada. Sem unidade, `unit=null` e marcado — não é comparável entre casos.
2. **Normalizar a superfície do número.** A amostra traz separador de milhar (*"12,476.5ng/ml"*), colagem sem espaço (*"6iu/ml"*) e unidade por extenso (*"6100 per microliter"*, PMC4835621_01). Guardar sempre o `raw_text` original.
3. **Unidades canônicas (UCUM) com dicionário de variantes.** `ng/ml` = `ng/mL`; `/mm3` = `per microliter` = `/µL`. Sem isso, consulta agregada não funciona.
4. **Faixa de referência é opcional** — só 21% dos casos a trazem, em quatro formatos: intervalo fechado (`0-0.04 ng/mL`), com `%` (`55%-75%`), limite aberto (`<20`, **sem unidade**, PMC3917415_01) e `<=10 AU/mL`.
5. **Interpretação: preferir a declarada.** Adjetivo de interpretação aparece em **91%** dos casos, contra 21% de faixa explícita. Se o texto declara (*"troponin was normal"*, *"CK-MB [...] elevated"*, PMC7102447_01) → `interpretation_source=stated`. Só derivar da faixa como reserva. **Nunca inferir por conhecimento clínico próprio.**
6. **Resultado qualitativo também é resultado.** *"positive Donath-Landsteiner test"* → `value=positive`, `unit=null`.
7. **Dose de medicamento tem esquema próprio** (`dose_value`/`dose_unit`/`frequency`/`route`), separado de `ExamResult` — é prescrição, não medição.
8. **Tamanho fica na entidade medida.** *"9.5cm x 4.5cm x 2.0cm cyst"* é atributo do `Finding`, não um `ExamResult`.
