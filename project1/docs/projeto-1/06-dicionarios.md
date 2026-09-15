# 06 — Dicionários, tesauros e ontologias

**Projeto:** MultiCaRe → grafo de conhecimento · MC896/Unicamp · PNL-CGGJL
**Estratégia:** ligação a vocabulário controlado (dicionários/tesauros/ontologias)
**Referência:** issue #6 — Parser caso → grafo · estratégia: dicionários
**Código:** [`project1/src/projeto-1/dicionarios/`](../../src/projeto-1/dicionarios/) (ver também o [README técnico](../../src/projeto-1/dicionarios/README.md), que documenta o pipeline processo a processo)

## 1. Objetivo

A issue #6 exige um programa independente que receba um `case_id`, leia o relato clínico em `project1/sample/cases.csv` e gere duas tabelas — nós e arestas — conforme o contrato comum das issues #3–#6. A característica obrigatória desta solução é a **ligação de entidades extraídas do texto a conceitos de um vocabulário controlado com código estável**, materializada no grafo como nós `Concept` e arestas `SAME_AS`.

Modelos de linguagem não participam de nenhuma etapa — extração é regra/regex, casamento é exato/aproximado sobre um dicionário derivado de uma fonte pública.

## 2. Escolha do vocabulário

| Vocabulário | Domínio | Licença/custo | Decisão |
|---|---|---|---|
| **MeSH** | termos médicos gerais (doenças, drogas, procedimentos, técnicas diagnósticas) | **Domínio público**, download direto da NLM, sem registro. Termos de uso exigem só atribuição — ver §3. | **Adotado** |
| UMLS Metathesaurus | agregador entre vocabulários | Exige registro/licença de uso na NLM (UTS), com termos adicionais por vocabulário-fonte agregado | Não adotado — barreira de registro sem necessidade, já que MeSH sozinho cobre bem o escopo escolhido |
| SNOMED CT | achados clínicos, sintomas, procedimentos | Licenciamento por país (via IHTSDO/SNOMED International); uso nos EUA é gratuito via licença afiliada da NLM, mas redistribuição de um gazetteer derivado exige verificar os termos dessa licença antes | Não adotado — cobertura de sintomas seria mais fina que a do MeSH, mas o custo de verificação/conformidade de licença não se paga para este projeto |
| LOINC | exames laboratoriais (códigos de teste, não do procedimento em si) | Gratuito, requer aceite de licença de uso (Regenstrief) | Não adotado — MeSH já cobre nomes de procedimento/técnica diagnóstica (categoria `E01`) suficientemente para o que os casos mencionam |
| ICD-10 | diagnósticos, para fins de codificação administrativa | OMS disponibiliza gratuitamente; WHO ICD-10 tem uso livre para fins não comerciais | Não adotado — MeSH (categoria `C`) já cobre nomenclatura de doença; ICD-10 agrega pouco para o texto narrativo de um caso clínico, sendo mais voltado a codificação administrativa |
| RxNorm | medicamentos (nomes normalizados, com relações a princípio ativo/marca) | NLM, gratuito, sem registro | Não adotado nesta entrega — MeSH (categoria `D`, Chemicals and Drugs) já cobriu os fármacos observados na amostra; RxNorm é o candidato natural para aprofundar `Medication` como **trabalho futuro**, especialmente para normalizar nome comercial → princípio ativo, o que o MeSH não faz |

**Justificativa da escolha final:** cobrir bem com um vocabulário só, em vez de tentar integrar vários parcialmente. O MeSH, sozinho, tem cobertura em quatro das seis categorias de entidade do doc 01 (`Diagnosis`/`History`/`Symptom`/`Finding` via categoria `C`; `Medication` via `D`; `Exam` via `E01`; `Treatment` via `E02`+`E04`; e diagnósticos psiquiátricos via `F03`), sem nenhuma barreira de licença, já está presente como referência em `metadata.csv` (`mesh_terms`), e é a mesma fonte que a validação cruzada (processo 7) usa como sinal independente — usar o mesmo vocabulário nos dois lados evita ter que reconciliar dois sistemas de código diferentes. RxNorm e SNOMED CT ficam documentados como extensão natural, não como lacuna ignorada.

`AnatomicalSite` não tem vocabulário oficial adotado nesta entrega — em vez disso, foi construído um **gazetteer próprio, do zero**, com código interno (`ANAT001`, `ANAT002`, ...). Essa é a segunda técnica que a issue permite demonstrar (vocabulário *construído*, em contraste com o MeSH, que é vocabulário *pronto*) — ver §4.1. `Patient`, `ExamResult` e `Outcome` não são candidatos a ligação de vocabulário (não são conceitos médicos catalogáveis, são o paciente em si ou valores/desfechos).

## 3. Situação de licença (MeSH)

Verificado na fonte oficial antes de implementar:

- **Fonte:** `desc2026.xml`, baixado de `https://nlmpubs.nlm.nih.gov/projects/mesh/MESH_FILES/xmlmesh/desc2026.zip` (NLM/National Library of Medicine, EUA). Arquivo de ~313 MB descompactado; **não versionado no repositório** (fica em `project1/src/projeto-1/dicionarios/data/`, ignorado pelo `.gitignore`) — só por tamanho, não por restrição de licença.
- **Termos de uso** ([nlm.nih.gov/databases/download/terms_and_conditions_mesh.html](https://www.nlm.nih.gov/databases/download/terms_and_conditions_mesh.html)): uso e redistribuição livres, exigindo apenas (1) atribuição clara à NLM como fonte; (2) não sugerir endosso da NLM; (3) se redistribuído, manter a versão atualizada ou indicar claramente a versão usada; (4) isenção de responsabilidade da NLM por erros nos dados. Sem exigência de registro, licença paga, ou restrição de uso por país.
- **Consequência prática:** o gazetteer *derivado* do MeSH (ver §4) pôde ser versionado no repositório sem problema de licença — ao contrário do que aconteceria com SNOMED CT ou UMLS, onde a redistribuição de um gazetteer derivado exigiria confirmar a licença específica do vocabulário-fonte antes.

**Atribuição:** este projeto usa dados do MeSH (Medical Subject Headings), National Library of Medicine, EUA.

## 4. Gazetteer

**Formato de extração.** `project1/src/projeto-1/dicionarios/mesh_parser.py` faz uma única passada em streaming pelo XML (`xml.etree.ElementTree.iterparse`, sem carregar a árvore inteira em memória) e extrai, por `DescriptorRecord`: `DescriptorUI` (código), `DescriptorName` (termo preferido), `TreeNumberList` (posição na hierarquia) e todos os `Term/String` de `ConceptList` (sinônimos/*entry terms*). 31.110 descriptors processados em ~3,6 s.

**Filtro por categoria.** Em vez de um gazetteer único com o MeSH inteiro (a maioria irrelevante — geografia, organismos, ocupações...), cada descriptor é mantido só nas categorias cujo `TreeNumber` bate com o prefixo relevante:

| Categoria interna | Prefixo(s) MeSH | Entidade(s) do doc 01 | Termos (com sinônimos) | Descriptors únicos |
|---|---|---|---:|---:|
| `diseases` | `C` (Diseases) | `Diagnosis`, `History`, `Symptom`, `Finding` | 58.284 | 5.069 |
| `drugs` | `D` (Chemicals and Drugs) | `Medication` | 94.012 | 10.688 |
| `exams` | `E01` (Diagnosis, sub-ramo de técnicas) | `Exam` | 7.787 | 784 |
| `treatments` | `E02`+`E04` (Therapeutics / Surgical Procedures) | `Treatment` | 11.076 | 1.236 |
| `mental_disorders` | `F03` (Mental Disorders) | `Diagnosis` (psiquiátrico) | 3.063 | 235 |

**Persistência: sempre cru, nunca normalizado.** `build_gazetteer_rows()` gera uma linha por `(termo, categoria)` **exatamente como está no MeSH** — sem lowercase, sem strip de pontuação. Essas 174.006 linhas ficam versionadas em `project1/src/projeto-1/dicionarios/gazetteer/mesh_gazetteer.csv` (11 MB). A normalização (§5) é aplicada só no momento de carregar o gazetteer para uso (`rows_to_raw_gazetteer()` + `normalization.build_normalized_gazetteer()`), como uma etapa separada e substituível — decisão deliberada para facilitar integração futura: se o projeto convergir numa normalização compartilhada entre as quatro issues, basta injetar a nova função (`normalize_fn=...`), sem regerar o gazetteer nem precisar do arquivo de 313 MB de novo.

### 4.1 Gazetteer próprio: `AnatomicalSite`

Construído sem bootstrap automático no MeSH — decisão deliberada de encarar a curadoria manual, não só cruzar uma lista já pronta contra o corpus. Método:

1. Pesquisa de referências de terminologia anatômica na internet: [SEER Training Modules](https://training.seer.cancer.gov/anatomy/body/terminology.html) (National Cancer Institute) e [Anatomy & Physiology, SUNY/Lumen Learning](https://courses.lumenlearning.com/suny-ap1/chapter/anatomical-terminology/) — usadas como matéria-prima, não como fonte única fechada.
2. Seleção manual de ~50 conceitos (órgãos e regiões corporais) relevantes ao domínio de relatos clínicos, escritos à mão em `anatomical_site_terms.py`, com sinônimo/forma adjetiva por **mapa explícito** (`stomach ↔ gastric`, `kidney ↔ renal`), não por regra automática de sufixo.
3. Cada conceito recebe um código interno (`ANAT001`, ...) e `vocabulary=local` no `Concept` gerado — nunca o código do MeSH, mesmo esse existindo pra anatomia (categoria `A`), justamente para manter o contraste pedagógico entre as duas técnicas.
4. Persistido, versionado, em `gazetteer/anatomical_site_gazetteer.csv` (101 linhas — conteúdo autoral, sem questão de licença).

**NER para esta entidade é mais simples que o resto do pipeline, de propósito:** como o vocabulário é pequeno e fechado (curado por nós), varrer o `case_text` direto contra o próprio gazetteer (`extractors/anatomical_site.py`) já é uma extração razoável — o risco de falso positivo que motivou o NER por gatilho nas outras entidades (§8) é bem menor aqui. Duas salvaguardas: (1) só vira nó se cair dentro do span de evidência de um `Symptom`/`Treatment` já extraído (sem isso não há como formar a aresta `LOCATED_IN`); (2) descartado se cair dentro do span de um `Diagnosis`, para não duplicar o órgão já embutido no nome da doença (`"pancreatitis"` não deve gerar `pancreas`).

**Bug real encontrado ao rodar isso pela primeira vez, que afeta o matching como um todo — não só esta entidade:** o threshold de fuzzy match (85, calibrado em §6 com termos médicos longos) não é seguro para chaves curtas. `fuzz.ratio("had", "head") = 85,7`; o mesmo para `"one"`/`"bone"`, `"fear"`/`"ear"`, `"year"`/`"ear"` — em todos os casos, uma única edição de caractere numa palavra comum do inglês já cruza o limiar, porque a métrica é proporcional ao tamanho total das strings, e strings curtas toleram muito menos edições antes de virarem "diferentes" na prática. Corrigido com `MIN_FUZZY_LENGTH = 5`: fuzzy match não roda mais para tokens/labels com menos de 5 caracteres. A correção também eliminou, de graça, um falso positivo pré-existente em `Medication` (`"that"` casando com `Tacrine`) que não tinha relação com anatomia — só ficou visível porque o novo gazetteer tem muito mais chave curta que o MeSH.

**Resultado nos 56 casos** (comparado antes/depois, `project1/src/projeto-1/dicionarios/output/` vs. `project1/src/projeto-1/dicionarios/output_v2/` — este último **não versionado**, por decisão do autor, pendente de revisão antes de substituir o oficial): **+18 nós `AnatomicalSite`, +18 arestas `LOCATED_IN`, +18 arestas `SAME_AS`** (cobertura de 100% nesta categoria — esperado, já que a própria extração é a varredura do dicionário), e **-1** aresta `SAME_AS` em outro lugar (o falso positivo do `"that"`/`Tacrine` corrigido). Termos encontrados: `abdomen`, `abdominal` (×4), `cardiac`, `chest` (×3), `dorsal`, `esophagus.`, `Esophageal`, `forearm`, `gastric`, `palm`, `pancreatic`, `pulmonary`, `skin`.

## 5. Normalização

Aplicada igualmente ao texto do caso e às chaves do gazetteer (`project1/src/projeto-1/dicionarios/normalization.py`):

1. Normalização Unicode (NFKC), antes da tokenização.
2. Tokenização (`nltk.word_tokenize`).
3. Por token: remoção de pontuação nas bordas + lowercase.
4. Tokens que normalizam para vazio (pontuação pura) são **descartados antes de formar qualquer janela de busca** — não apenas ignorados na hora de montar a chave. Um bug real foi encontrado e corrigido durante o desenvolvimento: sem esse descarte antecipado, um token de pontuação podia ser silenciosamente absorvido dentro do span casado (ex. `"constipation ."` em vez de `"constipation"`), risco de unir span através de fronteiras de frase.

**Deliberadamente sem** stemming, lematização ou remoção de stop-words: (a) atrapalhariam o casamento multi-palavra por janela, que depende de comparação exata token a token; (b) o MeSH já cataloga a maior parte da variação morfológica relevante como sinônimos (`"NIDDM"`, `"Type 2 Diabetes Mellitus"` e `"Diabetes Mellitus, Type 2"` resolvem para o mesmo código de graça); (c) a variação residual não coberta fica a cargo do fuzzy match (§6), que é a ferramenta certa para diferença real (não normalização de superfície).

A normalização nunca sobrescreve o texto original — só gera a chave de busca. O `label` do nó final mantém o texto tal como apareceu no caso.

## 6. Estratégia de casamento

Implementada em `project1/src/projeto-1/dicionarios/matching.py`, três técnicas em ordem de rigor decrescente:

1. **Exact match** — string idêntica após normalização.
2. **Longest match** — janela de tokens decrescente (tenta a sequência mais longa primeiro); cobre conceitos multi-palavra. Exact match é, na implementação, só o caso particular de janela de tamanho 1.
3. **Fuzzy match** — só para o que sobra sem casar nas duas etapas acima, e só span a span (não em janelas multi-palavra — decisão de manter o escopo simples, já que o MeSH cobre a maior parte da variação de fraseado como sinônimo). Usa `rapidfuzz.fuzz.ratio` (distância de edição normalizada).

**Threshold do fuzzy match: 85**, escolhido empiricamente. Testado com erros de digitação reais de termos que sabíamos existir no MeSH (`pancreatits`, `naussea`, `hypertention`, `diabetis mellitus type 2`) contra palavras que não deveriam casar (`flank`, `she`):

| entrada | melhor casamento | score |
|---|---|---:|
| `pancreatits` | pancreatitis | 95,7 |
| `abdominal pian` | abdominal pain | 92,9 |
| `naussea` | nausea | 92,3 |
| `hypertention` | hypertension | 91,7 |
| `diabetis mellitus type 2` | diabetes mellitus type 2 | 95,8 |
| `flank` (não deveria casar) | flank pain | 66,7 |
| `she` (não deveria casar) | rash | 57,1 |

Os verdadeiros positivos ficam em 91–96; os que não deveriam casar, em 57–67. **85** fica com folga segura entre os dois grupos — **para strings desse comprimento**. A folga não se sustenta para chaves curtas (ver §4.1): `fuzz.ratio` é proporcional ao tamanho total das duas strings, então uma única edição de caractere numa palavra de 3-4 letras já produz uma similaridade de 85%+, mesmo sem nenhuma relação semântica (`"had"` vs `"head"` = 85,7). Corrigido com `MIN_FUZZY_LENGTH = 5`: abaixo desse tamanho, fuzzy match nem é tentado — só exact/longest decidem.

**Desempate.** Quando uma chave normalizada aponta para mais de um conceito — checado contra os dados reais, não hipotético: existe **exatamente 1 caso em 58.062 chaves** da categoria `diseases` (`"anemia hypoplastic congenital"`, que aponta tanto para `D029502` "Anemia, Hypoplastic, Congenital" quanto para `D029503` "Anemia, Diamond-Blackfan"). Regra: preferir o concept cujo `preferred_term` normaliza exatamente para a mesma chave (o termo canônico daquele concept, não um sinônimo emprestado de outro); resolve o caso real corretamente (`D029502`). Sem candidato canônico único, desempata pelo código em ordem alfabética, por determinismo.

## 7. Ligação ao grafo

Cada entidade extraída (por um NER simples baseado em gatilho léxico — ver §8) que casa com um conceito gera um nó `Concept` (`vocabulary`, `code`, `preferred_term`) e uma aresta `SAME_AS`. O mesmo `Concept` é reaproveitado dentro do caso quando duas entidades diferentes casam com o mesmo código (ex. um `Symptom` e uma `History` mencionando o mesmo conceito), em vez de duplicar o nó. Menção sem casamento continua como nó normal, sem `Concept`/`SAME_AS` — cobertura parcial esperada e documentada, não erro.

## 8. Por que o NER continua necessário (mesmo não sendo a técnica obrigatória)

Cogitou-se varrer o `case_text` inteiro direto contra o gazetteer, sem nenhuma etapa prévia de reconhecimento de entidade — e essa ideia foi descartada, por quatro motivos concretos:

1. **Cobertura zero para o que não está no MeSH.** Sem uma etapa que decida "isso é uma menção candidata" independentemente do dicionário, qualquer termo não catalogado nunca chega a virar nó, nem sem `Concept` — na prática, o contrato ("menção sem match ainda vira nó normal") fica sem sentido, porque não existe "menção" para começar.
2. **O dicionário não informa atributos.** `polarity`, `duration`, `certainty` vêm do contexto textual ao redor da menção (gatilhos), não do MeSH.
3. **O mesmo conceito muda de tipo de entidade pelo contexto, não pelo termo.** `"history of hypertension"` → `History`; `"diagnosed with hypertension"` → `Diagnosis`; o dicionário sozinho não decide isso.
4. **Risco de falso positivo maior sem uma âncora de contexto** confirmando a intenção da menção.

Por isso o pipeline implementa um NER simples, baseado em gatilho léxico e regex (`project1/src/projeto-1/dicionarios/extractors/`) — no nível do que a issue #4 (normalização) já validou como suficiente, não no nível de sofisticação sintática da issue #5 (POS-tagging), que não é o foco desta entrega. NER aqui é infraestrutura de apoio para chegar ao entregável, não a técnica que este trabalho precisa demonstrar dominar.

## 9. Resultados sobre a amostra (56 casos)

Pipeline completo executado sem exceção nos 56 casos de `project1/sample/cases.csv` (`project1/src/projeto-1/dicionarios/batch.py`). Duas versões das tabelas existem: `project1/src/projeto-1/dicionarios/output/` (versionado, sem `AnatomicalSite`) e `project1/src/projeto-1/dicionarios/output_v2/` (não versionado, já com `AnatomicalSite` e a correção do `MIN_FUZZY_LENGTH` — ver §4.1); a decisão de qual vira a oficial fica pendente de revisão.

**Nós gerados (com `AnatomicalSite`, `project1/src/projeto-1/dicionarios/output_v2/`):** 56 `Patient`, 64 `Symptom`, 48 `History`, 46 `Diagnosis`, 41 `Treatment`, 41 `Medication`, 33 `Outcome`, 30 `Exam`, 18 `AnatomicalSite`, **135 `Concept`**.

**Cobertura do casamento:** das 288 entidades de tipo ligável (`Symptom`/`History`/`Diagnosis`/`Exam`/`Treatment`/`Medication`/`AnatomicalSite`), **139 geraram aresta `SAME_AS` (48,3%)**. Maior que o achado análogo de um colega usando léxico+POS-tagging (14% dos sintagmas dele tinham tipo no léxico) — plausível, já que aqui o matching já é restrito à categoria certa do vocabulário por tipo de entidade, em vez de comparar contra um léxico genérico. `AnatomicalSite` sozinho tem cobertura de 100% — resultado estrutural, não uma vitória de precisão: como o NER dessa entidade *é* a varredura do dicionário (§4.1), todo nó criado já bateu com uma chave por definição.

**Validação cruzada (processo 7):** 8 dos 50 artigos têm `mesh_terms` vazio (excluídos). Dos 48 restantes, sobreposição média de só **1,1%** dos termos do artigo, com overlap positivo em **6,2%** dos casos. Baixo, mas consistente com o aviso do próprio enunciado — `mesh_terms` descreve o artigo, não o caso. Quebrando por tipo de entidade de origem, a hipótese se confirma: `Diagnosis` (8,7%), `Treatment` (16,7%) e `Exam` (14,3%) batem mais que `Symptom` (0%) e `History` (0%) — curadores indexam pelo tema clínico do artigo, não por cada sintoma do caso.

## 10. Limitações conhecidas e trabalho futuro

| Limitação | Efeito | Observação |
|---|---|---|
| `"CT"` não é sinônimo cadastrado de `Tomography, X-Ray Computed` no MeSH | Siglas curtas/ambíguas do próprio caso não casam via dicionário | Precisam ser resolvidas por expansão local (`termo por extenso (SIGLA)`), não implementado nesta entrega |
| Match genérico em vez de específico (`"contrast enhanced computed tomography"` → `Tomography` `D014054`, não `Tomography, X-Ray Computed` `D014057`) | `Concept` perde especificidade quando só uma sub-palavra do span casa | Não é erro do algoritmo — o MeSH simplesmente não cataloga a frase composta como sinônimo do descriptor mais específico |
| NER simples por gatilho léxico | Constructions como `"past medical, family and medication history were otherwise non-contributory"` (sujeito antes do gatilho "history") não são reconhecidas | Aceitável: fica silencioso (não gera nó incorreto), só não gera nó nenhum — trade-off consciente de manter o NER simples |
| `AnatomicalSite` ancorado só em `Symptom`/`Treatment` | Sítio mencionado num trecho de `Finding` (não implementado) fica sem `LOCATED_IN` e não vira nó — ex. `"stomach"`/`"pancreas"` em `"a cystic lesion between the stomach and [...] pancreas"` | Consequência direta de não termos implementado o extractor de `Finding` (§8); reduz a superfície de ancoragem, não a qualidade do que é encontrado |
| Label de `AnatomicalSite` às vezes inclui pontuação colada (`"esophagus."`) | Cosmético — o conceito casado continua correto | Limite de tokenização (`TreebankWordTokenizer`), não corrigido nesta entrega |
| Threshold de fuzzy match não é seguro para chaves curtas | Falso positivo em gazetteers com muita chave de 3-4 letras (ex. `"had"`→`"head"`) | Corrigido com `MIN_FUZZY_LENGTH=5` (ver §4.1/§6) — documentado aqui como lição, não como lacuna aberta |
| RxNorm/SNOMED CT/LOINC/ICD-10 não integrados | Cobertura de `Medication`/`Symptom`/`Exam`/`Diagnosis` limitada ao que o MeSH cataloga | Documentado em §2 como extensão natural, não lacuna ignorada — MeSH sozinho já cobre 4 das 6 categorias linkáveis |
| Fuzzy match só span a span, não em janelas multi-palavra | Erro de digitação numa frase de mais de uma palavra não é corrigido | Decisão de escopo: MeSH já cataloga a maior parte da variação de fraseado relevante como sinônimo |

## 11. Referências

- Issue #6 — Parser caso → grafo · estratégia: dicionários.
- [README técnico do pipeline](../../src/projeto-1/dicionarios/README.md) — descrição processo a processo, com todos os testes e achados intermediários.
- [Dados a extrair](01-dados-a-extrair.md).
- [Esquema do grafo](02-esquema-grafo.md).
- National Library of Medicine — [MeSH XML Data Files](https://www.nlm.nih.gov/mesh/xmlmesh.html), [Terms and Conditions](https://www.nlm.nih.gov/databases/download/terms_and_conditions_mesh.html).
- [SEER Training Modules — Anatomical Terminology](https://training.seer.cancer.gov/anatomy/body/terminology.html), National Cancer Institute — referência para o gazetteer próprio de `AnatomicalSite` (§4.1).
- [Anatomy & Physiology I — Anatomical Terminology](https://courses.lumenlearning.com/suny-ap1/chapter/anatomical-terminology/), SUNY / Lumen Learning — idem.
