# Estratégia de tokenização

Pipeline clássico e baseado em regras para converter um caso clínico do
MultiCaRe em tokens, nós e arestas.

## Instalação

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r project1/src/tokenizacao/requirements.txt
```

O NLTK é usado apenas na abordagem comparativa `treebank`. O tokenizador
principal `clinical_regex` usa somente a biblioteca padrão do Python.

## Gerar tokens e grafo de um caso

```bash
python3 project1/src/tokenizacao/main.py \
  --cases project1/sample/cases.csv \
  --case-id PMC5137649_01 \
  --tokenizer clinical_regex \
  --output project1/src/tokenizacao/output
```

Arquivos produzidos:

- `<case_id>-tokens.csv`: tokens, tipos e offsets;
- `<case_id>-nodes.csv`: tabela de nós do contrato comum;
- `<case_id>-edges.csv`: tabela de arestas do contrato comum.
- `<case_id>-graph.md`: visualização Mermaid completa;
- `<case_id>-graph-slide.md`: recorte legível para a apresentação.

## Comparar as abordagens

No mesmo caso:

```bash
python3 project1/src/tokenizacao/main.py \
  --cases project1/sample/cases.csv \
  --case-id PMC5137649_01 \
  --compare
```

Em toda a amostra:

```bash
python3 project1/src/tokenizacao/main.py \
  --cases project1/sample/cases.csv \
  --evaluate-sample
```

## Testes

```bash
python3 -m unittest discover -s project1/src/tokenizacao/tests -v
```

A explicação completa do algoritmo, das decisões, dos resultados e das falhas
está em [`docs/03-tokenizacao.md`](../../docs/03-tokenizacao.md).
