# Projeto 2 — extração estatística de grafos clínicos

Continuação do projeto 1 conforme o [enunciado da disciplina](https://github.com/santanche/nlp2learn/tree/main/projects/2026/project2).
Implementa os módulos da [issue #32](https://github.com/caiomelloni/PNL-CGGJL/issues/32): leitura e
processamento de texto compartilhados, termos compostos e montagem do grafo.

## Começar pela amostra

Python 3.10+. A execução em CSV usa a biblioteca padrão e o HMM versionado no projeto 1.
Execute da raiz do repositório. A amostra tem 56 casos; os 3 casos do gabarito mock da etapa 2
são excluídos da contagem. A lista de avaliação definitiva precisa ser consolidada com a #29.

```bash
python3 -m project2.src.termos.termos gerar --gold project2/data/mock/gold/casos.txt --saida project2/data/demo/termos.csv
python3 -m project2.src.termos.termos comparar --termos project2/data/demo/termos.csv --saida project2/data/demo/comparacao.csv --top 100
python3 -m unittest discover -s project2/tests -v
```

Os resultados preliminares estão em [experimentos/amostra/](experimentos/amostra/).
A metodologia e as limitações estão em [docs/etapa-1.md](docs/etapa-1.md).

## Módulos entregues

| Módulo | Responsabilidade | Instruções |
|---|---|---|
| `src/comum/` | Casos, tokens, frases, HMM, lista do gabarito e coleta do corpus | [README](src/comum/README.md) |
| `src/termos/` | Contagens em disco, PMI, C-value e comparação MeSH | [README](src/termos/README.md) |
| `src/montagem/` | Tabelas das etapas 3/4 → CSVs e visualizador P1 | [README](src/montagem/README.md) |

## Corpus completo

```bash
python3 -m venv project2/.venv
project2/.venv/bin/python -m pip install -r project2/src/comum/requirements.txt
project2/.venv/bin/python -m project2.src.comum.coletar
```

No Windows, use `project2/.venv/Scripts/python.exe`. A coleta grava em `project2/data/corpus/`
e registra a versão e os checksums em `proveniencia.json`. Dados e ambiente virtual ficam fora do Git.

Depois de confirmar a lista definitiva em `project2/data/gold/casos.txt`:

```bash
python3 -m project2.src.termos.termos gerar --corpus project2/data/corpus/csv/full/cases.csv --freq-min 5
python3 -m project2.src.termos.termos comparar --top 100
```

Isso gera `data/termos.csv`, `data/termos.json`, `data/resultados/termos.csv` e `data/resultados/termos.json`.
O comando exige a lista de IDs para excluir os casos de avaliação.

O leitor já foi validado nos 98.641 casos do Parquet completo da versão 3.0.1: todos os 56 textos
da amostra foram encontrados sem alterações. O [registro da validação](experimentos/amostra/validacao_corpus.json)
é independente do experimento de termos, que continua preliminar e limitado à amostra.
O tokenizador também passou pelos 98.641 casos, produzindo 51.804.708 tokens sem falhas após
a correção de `_` isolado. O ranking da amostra permaneceu idêntico.

## Integração e pendências do grupo

O PR #31 trouxe `data/gold/casos.txt` com 8 casos, todos presentes na amostra do P1.
A #29 descreve 16 casos externos à amostra. É preciso consolidar esse protocolo antes do
experimento definitivo. Os resultados abaixo continuam usando apenas o gold mock indicado.

Os módulos da etapa 5 agora estão em `src/montagem/data`, `evaluation` e `assembly`.
O [README da etapa 5](src/montagem/README-etapa5.md) preserva seus comandos. O montador
`src/montagem/montagem.py` desta entrega consome o contrato das etapas 3/4; a integração
com a rota `assembly` ainda precisa ser definida pelo grupo.

As APIs do módulo comum seguem as usadas nos mocks do Caio. A migração dos imports e dos caminhos
nas etapas 2/3 está descrita no [README do comum](src/comum/README.md#integrar-com-as-etapas-2-e-3).
O leitor `ler_termos()` é compatível com a lista de tuplas esperada pelo CRF.

A montagem exige as saídas reais `mencoes_tipadas.csv` e `relacoes.csv`. A versão atual do PR #38
ainda não grava `polaridade` e pode deixar `tipo` vazio. Existem opções explícitas de integração,
com contagens no resumo, no [README da montagem](src/montagem/README.md).

Pendências:

- Consolidar a lista definitiva do gabarito (#29) e gerar os termos no corpus completo.
- Anotar os 3 casos individuais e o caso compartilhado.
- Integrar a lista de termos ao CRF e avaliar o modelo com e sem essa pista.
- Montar os grafos com as saídas finais das etapas 3/4 e avaliar no gabarito oficial.

## Métodos

A extração utiliza regex, o HMM do projeto 1, contagens, PMI e C-value.
O processamento dos casos não utiliza LLMs, embeddings ou Transformers.
