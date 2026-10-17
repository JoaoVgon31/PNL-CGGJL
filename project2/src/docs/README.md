# Documentação do Código-Fonte · Projeto 2 (`project2/src/docs/`)

Este diretório reúne os relatórios técnicos e a documentação interna da arquitetura e implementação dos módulos de `project2/src/`.

---

## Documentos Disponíveis

* **[Relatório Técnico · Estação 5: Dados, Avaliação e Montagem](relatorio_estacao_5.md)**  
  Relatório completo com a arquitetura dos módulos desenvolvidos por George Henrique (Estação 5):
  1. **Visão Geral e Responsabilidades**
  2. **Implementação Técnica dos Módulos:**
     * `splits.py` (partição determinística de casos)
     * `weak_supervision.py` (supervisão fraca e datasets silver)
     * `gold_manager.py` (validação e curadoria do gabarito ouro)
     * `metrics.py` e `evaluate.py` (métrica comum oficial e confronto experimental)
     * `clustering.py`, `graph_builder.py` e `pipeline.py` (montagem de grafos e deduplicação)
  3. **Guia de Execução: Como gerar os arquivos em `project2/data/processed/`**
  4. **Qualidade de Código e Testes Automatizados** (23 testes unitários)
  5. **Resultados Quantitativos e Métricas Experimentais**
  6. **Conclusões e Próximos Passos**
