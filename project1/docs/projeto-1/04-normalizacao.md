# Issue 4 — Relatório implementação da normalização

**Projeto:** MultiCaRe → grafo de conhecimento · MC896/Unicamp · PNL-CGGJL  
**Estratégia:** normalização por regras clássicas de PNL  
**Referência:** [issue 4 — Parser caso → grafo · estratégia: normalização](https://github.com/caiomelloni/PNL-CGGJL/issues/4)  

## 1. Objetivo

A issue 4 exige um programa independente que receba um `case_id`, leia o relato clínico em `sample/cases.csv` e gere duas tabelas: uma de nós e outra de arestas. A característica obrigatória desta solução é uma camada explícita de normalização entre o texto extraído e o `label` final dos nós.

A implementação está em `src/projeto-1/normalizacao/` e usa regras, expressões regulares e dicionários. Modelos de linguagem não participam da extração dos dados, em conformidade com a restrição do projeto.

## 2. Principais implementações

### Leitura e validação da entrada

O leitor localiza o caso pelo identificador, preserva o texto original e valida colunas obrigatórias, IDs duplicados e idade inválida.

### Normalização textual

Os rótulos passam por uma sequência controlada:

1. normalização Unicode NFKC;
2. redução de espaços repetidos;
3. remoção apenas da pontuação nas extremidades;
4. `case folding`;
5. restauração da grafia canônica de termos sensíveis, como `CA 19-9`, `HER2`, `pH`, `IgG`, `IgM` e `IgA`.

Essa estratégia reduz variações superficiais sem remover indiscriminadamente pontuação interna ou diferenças clínicas relevantes. Não foram aplicados stemming, lematização nem remoção global de stop-words, pois essas operações poderiam alterar o significado ou os limites das entidades.

### Siglas locais ao caso

O sistema reconhece definições no padrão `termo por extenso (SIGLA)` e usa esse vocabulário apenas no relato em que foi descoberto. Menções equivalentes podem, assim, convergir para o mesmo rótulo, enquanto siglas desconhecidas são preservadas em vez de receberem uma expansão inventada.

### Números, unidades e faixas

Valores são convertidos com `Decimal`, preservando precisão e separando valor, unidade e texto original. Um dicionário de variantes converte formas como `ng/ml` e `per microliter` para unidades canônicas como `ng/mL` e `/µL`. Também há reconhecimento de faixas abertas e fechadas e uma primeira classificação de resultados como aumentados, reduzidos ou normais.

### Extração e construção do grafo

O pipeline possui regras para paciente, antecedentes, sintomas, exames, resultados, achados, diagnósticos, medicamentos, tratamentos, locais anatômicos e desfechos. O construtor:

- cria IDs por tipo de nó e IDs sequenciais de aresta;
- valida tipos e relações contra listas fechadas;
- normaliza o rótulo antes da inclusão;
- deduplica entidades somente quando rótulo e atributos de identidade são compatíveis;
- preserva eventos diferentes, como mudanças de dose e resultados repetidos;
- registra evidência, offsets e gatilhos nas relações.

### Exportação e impacto

A execução gera os CSVs de nós e arestas exigidos pelo contrato, um JSON com o impacto da normalização e uma visualização Mermaid auxiliar. No caso `PMC5137649_01`, foram processadas 40 menções, que produziram 33 chaves brutas e 32 nós finais; 7 rótulos mudaram e 1 par de nós foi fundido. A saída existente contém 32 nós e 42 arestas.

A suíte automatizada possui 151 testes. Eles cobrem leitura, normalização, siglas, unidades, entidades, relações, deduplicação, serialização e execução pela linha de comando.

## 3. Erros identificados durante a implementação

Apesar de o pipeline executar e passar nos testes atuais, a inspeção de casos reais revelou erros que ainda afetam a fidelidade do grafo:

| Erro observado | Efeito na saída |
|---|---|
| `level of 6iu/ml` interpretado como medicamento | Cria uma prescrição inexistente a partir de um resultado laboratorial. |
| `no mucosal abnormalities` e `without any complications` com polaridade afirmativa | Transforma fatos negados em achados ou desfechos presentes. |
| Diagnóstico `gdc (figs 3-5` | Incorpora referência editorial ao rótulo clínico. |
| Rótulo `12476.5 ng/ml` com atributo `unit=ng/mL` | Produz formas canônicas inconsistentes dentro do mesmo nó. |
| Medida `9.5cm x 4.5cm x 2.0cm` reduzida a `2.0cm` | Perde dimensões e pode associar o tamanho ao achado errado. |
| Ponto decimal tratado como fim de sentença | Recorta evidências e desloca os offsets. |
| Fonte `lab` preenchida sem pista textual | Acrescenta informação que o relato não sustenta. |
| Relações `SUPPORTS` e `REVISES` baseadas principalmente em proximidade | Podem conectar o achado ou diagnóstico ao alvo errado. |
| Limites `<` e `<=` tratados da mesma forma em certas comparações | Pode classificar incorretamente valores na fronteira da faixa. |
| Dependência de valor numérico com unidade | Omite resultados qualitativos, como `test was positive`. |

## 4. Possíveis implementações e melhorias

As próximas correções podem ser organizadas pela dependência e pelo impacto:

1. **Centralizar segmentação e offsets.** Criar um único segmentador que proteja decimais, abreviações e referências editoriais. Todas as entidades e relações devem reutilizar objetos de span derivados do texto original, garantindo `case_text[char_start:char_end] == evidence_text`.

2. **Melhorar o escopo de contexto e negação.** Separar primeiro o núcleo da menção e depois calcular polaridade, certeza e tempo sobre a oração correspondente. Testes de regressão devem cobrir modificadores entre o negador e o termo clínico.

3. **Tipar medições antes de classificá-las.** Representar valor, unidade, faixa, dose e dimensões em estruturas próprias. O rótulo final deve ser formatado a partir desses campos canônicos, sem normalizar novamente a unidade como texto genérico.

4. **Adicionar medidas multidimensionais e resultados qualitativos.** Reconhecer sequências `a x b x c unidade`, valores sem unidade em contextos controlados e estados como `positive`, `negative`, `reactive` e `non-reactive`.

5. **Fortalecer as relações.** Exigir compatibilidade de tipos, gatilho textual e vínculo sintático ou de oração. `REVISES` deve depender de evidência de substituição diagnóstica, não apenas da sequência “suspeito” seguida de “confirmado”.

6. **Representar eventos explicitamente.** Exames repetidos, alterações de dose e intervenções planejadas ou realizadas devem permanecer separados mesmo quando compartilham o mesmo conceito normalizado.

7. **Não inventar atributos ausentes.** Campos como fonte, certeza e estágio devem ficar vazios quando não houver evidência. A ausência de informação não pode ser convertida automaticamente em `lab`, `confirmed`, `initial` ou outro valor padrão.

8. **Construir uma referência humana.** Anotar uma amostra de casos e medir separadamente detecção de entidades, normalização, atributos, identidade e relações. Isso permitirá calcular precisão, revocação e F1 e diferenciar estabilidade estrutural de qualidade semântica.

## 5. Referências

- [Issue 4 — Parser caso → grafo · estratégia: normalização](https://github.com/caiomelloni/PNL-CGGJL/issues/4).
- [Relatório técnico completo da normalização](04-normalizacao-completo.md).
- [Dados a extrair](01-dados-a-extrair.md).
- [Esquema do grafo](02-esquema-grafo.md).
