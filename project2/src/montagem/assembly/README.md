# Módulo de Montagem do Grafo Final (`project2/src/montagem/assembly/`)

Este módulo implementa a consolidação, agrupamento hierárquico e montagem em lote dos grafos clínicos do Projeto 2.

---

## Como Executar

### 1. Montagem em Lote dos Grafos Clínicos (`pipeline.py`)

Para processar todos os 56 casos da amostra e gerar os nós e arestas canônicos:

```bash
python -m project2.src.montagem.assembly.pipeline
```

### 2. Opções Customizadas do CLI
```bash
python -m project2.src.montagem.assembly.pipeline \
    --entities project2/data/silver/entidades_tipadas.csv \
    --relations project2/data/silver/relacoes.csv \
    --output project2/data/processed \
    --case-ids PMC11259348_01,PMC11723754_01
```

---

## Arquivos Gerados em `project2/data/processed/`

* `<case_id>-nodes.csv`: Nós consolidados e deduplicados por similaridade de N-gramas (TF-IDF + Jaro-Winkler), com dimensões clínicas extraídas em atributos estruturados (ex: `size=6 cm`, `mentions=t2|t5`).
* `<case_id>-edges.csv`: Relações clínicas entre entidades mapeadas para nós canônicos, com polaridade e certeza.
* `_resumo.csv`: Tabela geral com contagem de nós, arestas e status de montagem de cada caso clínico.
