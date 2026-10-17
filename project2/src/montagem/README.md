# Montagem · Estação 5: Dados, Avaliação e Montagem

**Projeto 2 · Processamento de Linguagem Natural (MC896 / 2026.2)**  
Módulo responsável pelo hub de dados de treino/validação/teste (*Silver Standard*), curadoria do gabarito ouro (*Gold Standard*), métrica comum de avaliação experimental e esteira de clustering hierárquico e montagem do grafo clínico consolidado por caso.

---

## 📁 Estrutura do Pacote

- `data/`: partição determinística de casos (`splits.py`), supervisão fraca (`weak_supervision.py`) e consolidação do gabarito ouro (`gold_manager.py`);
- `evaluation/`: framework de métricas formais de avaliação (`metrics.py`) e CLI unificado para todas as estações (`evaluate.py`);
- `assembly/`: normalização de rótulos e dimensões clínicas, clustering hierárquico de menções (`clustering.py`), montador de grafos canônicos (`graph_builder.py`) e orquestrador em lote (`pipeline.py`);
- `docs/`: relatório técnico oficial ([`relatorio_estacao_5.md`](docs/relatorio_estacao_5.md)) e guia de anotação manual ([`guia-anotacao.md`](docs/guia-anotacao.md));
- `*/tests/`: suíte de 23 testes automatizados (unitários e integração).

---

## 🚀 Execução

A partir da raiz do repositório:

### 1. Montagem em Lote dos Grafos Clínicos (`processed/`)
```bash
python -m project2.src.montagem.assembly.pipeline
```
Gera os arquivos canônicos `<case_id>-nodes.csv`, `<case_id>-edges.csv` e `_resumo.csv` em `project2/data/processed/`.

### 2. Geração da Partição e Supervisão Fraca (`silver/`)
```bash
# Splits determinísticos de casos (splits.json)
python -m project2.src.montagem.data.splits

# Supervisão fraca (tempo de execução: ~40 segundos)
python -m project2.src.montagem.data.weak_supervision
```

### 3. Avaliação contra o Gabarito Ouro e Confronto Experimental
```bash
# Avaliação de predições
python -m project2.src.montagem.evaluation.evaluate --task all

# Confronto oficial entre regras (P1) e aprendizado de máquina (P2)
python -m project2.src.montagem.evaluation.evaluate --compare
```

---

## 🧪 Testes Automatizados

Para executar os 23 testes unitários do módulo:

```bash
python -m unittest discover -s project2/src/montagem -p "test_*.py"
```

---

## 📖 Documentação Detalhada

* [Relatório Técnico da Estação 5](docs/relatorio_estacao_5.md)
* [Guia Rápido de Anotação do Gabarito Ouro](docs/guia-anotacao.md)
