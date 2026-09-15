# Dicionários, tesauros e ontologias — issue #6

Parser de caso clínico → grafo de conhecimento, com as entidades **ligadas a vocabulário controlado** (MeSH + um gazetteer próprio de `AnatomicalSite`).

> Documentação detalhada — decisões, licença do MeSH, calibração dos thresholds, resultados e discussão — em [`docs/06-dicionarios.md`](../../docs/06-dicionarios.md). Este README é só o manual de uso.

## O que foi feito, e para que serve

O NER por regras decide **quais trechos do caso são entidades**; o dicionário entra depois e responde **"essa menção corresponde a algum conceito catalogado?"**. Quando corresponde, a entidade ganha um nó `Concept` (`vocabulary`, `code`, `preferred_term`) e uma aresta `SAME_AS`.

Isso é o que transforma um grafo de strings num grafo consultável: `"T2DM"` num caso e `"type 2 diabetes mellitus"` em outro deixam de ser dois rótulos diferentes e passam a apontar para o mesmo código (`D003924`), o que permite agrupar, contar e cruzar casos por conceito em vez de por grafia. Menção sem casamento continua virando nó normal — só não ganha `Concept`.

Em números, nos 56 casos da amostra: **48,3% das entidades ligáveis** geraram `SAME_AS` (139 de 288), produzindo 135 nós `Concept`.

O pipeline, em ordem: leitura do caso → normalização (NFKC + lowercase + pontuação das bordas) → NER por gatilho léxico (`presented with`, `diagnosed with`, `underwent`, ...) → casamento contra o gazetteer (exact → longest → fuzzy, `rapidfuzz`, threshold 85 e mínimo de 5 caracteres) → materialização de `Concept`/`SAME_AS` → validação cruzada contra os `mesh_terms` do artigo.

## Como rodar

Dependências (Python 3.10+):

```bash
pip install nltk rapidfuzz
python -c "import nltk; nltk.download('punkt_tab')"
```

Os gazetteers já vêm versionados em `gazetteer/` — **não é preciso baixar o MeSH** para rodar o pipeline. Os comandos abaixo rodam da raiz do repositório e assumem a amostra em `project1/sample/` (não versionada).

**Um caso:**

```bash
python project1/src/dicionarios/main.py --cases project1/sample/cases.csv --case-id PMC5137649_01
```

**Todos os casos da amostra, com o relatório de validação cruzada:**

```bash
python project1/src/dicionarios/batch.py --cases project1/sample/cases.csv --metadata project1/sample/metadata.csv
```

**Regerar o gazetteer próprio de `AnatomicalSite`** (a partir da lista curada em `anatomical_site_terms.py`):

```bash
python project1/src/dicionarios/build_anatomical_gazetteer.py
```

Para regerar o gazetteer do MeSH é preciso o `desc2026.xml` da NLM (~313 MB, não versionado) e chamar `mesh_parser.build_gazetteer_rows()`.

## O que é produzido

Tudo em `output/` (`--output` muda o destino):

| Arquivo | Conteúdo |
|---|---|
| `<case_id>-nodes.csv` | `case_id, node_id, type, label, attributes` — um por caso, incluindo os nós `Concept` |
| `<case_id>-edges.csv` | `case_id, edge_id, source_id, target_id, relation, attributes` — inclui as arestas `SAME_AS` e `LOCATED_IN` |
| `_crossval_summary.csv` | só no modo lote: por caso, nº de nós/arestas, conceitos casados e sobreposição com os `mesh_terms` do artigo |

Entradas versionadas em `gazetteer/`: `mesh_gazetteer.csv` (174.006 termos do MeSH, cru) e `anatomical_site_gazetteer.csv` (50 conceitos curados à mão, códigos `ANAT001`...).

> As tabelas atualmente em `output/` são a rodada **anterior** à inclusão de `AnatomicalSite`; a versão com essa entidade existe localmente mas não foi versionada — decisão pendente (ver §9 do doc).

## Onde a estratégia falha

- **O que o vocabulário não cataloga, não casa.** Siglas curtas e ambíguas ficam de fora do MeSH (`"CT"` não é sinônimo cadastrado de `Tomography, X-Ray Computed`) — resolver isso exigiria expansão local do tipo `termo por extenso (SIGLA)`, não implementada.
- **Casamento genérico demais.** `"contrast enhanced computed tomography"` casa com o descriptor genérico `Tomography` (`D014054`), não com o específico `D014057`. O `Concept` fica correto, mas perde especificidade.
- **`Symptom`/`History` quase não batem com o vocabulário do artigo.** A validação cruzada dá sobreposição média de 1,1% com os `mesh_terms`: `Diagnosis`/`Treatment`/`Exam` batem (8–17%), sintoma e histórico dão 0%. Isso é diferença de granularidade — o `mesh_terms` indexa o artigo, não o caso — e por isso serve como sinal, nunca como gabarito.
- **Fuzzy match é frágil em chave curta.** `fuzz.ratio("had", "head") = 85.7` cruzava o threshold e gerava falso positivo; contornado com `MIN_FUZZY_LENGTH = 5`, o que em troca desliga a correção de erro de digitação em termos curtos. O fuzzy também só roda span a span, nunca em janela multi-palavra.
- **A cobertura depende do NER, não do dicionário.** Gatilho léxico é simples de propósito: construções como `"past medical, family and medication history were otherwise non-contributory"` não são reconhecidas — o pipeline fica silencioso (não gera nó errado, só não gera nó).
- **`AnatomicalSite` só existe ancorado.** Um sítio só vira nó se cair no span de um `Symptom`/`Treatment` já extraído; como não implementamos `Finding`, sítios mencionados em trechos descritivos se perdem. Os 100% de cobertura dessa entidade são estruturais — o NER dela *é* a varredura do dicionário —, não uma medida de precisão.
- **Só MeSH.** RxNorm, SNOMED CT, LOINC e ICD-10 não estão integrados; `Patient`, `ExamResult` e `Outcome` não têm vocabulário associado nenhum.
