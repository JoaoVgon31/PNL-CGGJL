# Pipelines do Projeto 2

O pipeline completo do Projeto 2 foi estruturado em módulos Python em [`src/`](../src/) para permitir execução desacoplada, reprodutibilidade e testes unitários automatizados.

Para uma demonstração interativa passo a passo, veja o notebook:
- [`notebooks/pipeline_projeto2.ipynb`](notebooks/pipeline_projeto2.ipynb)

## Execução Sequencial

Para reproduzir o pipeline ponta a ponta a partir da raiz do repositório:

1. **Etapa 1 — Extração de Termos Compostos e Associações MeSH:**
   ```bash
   python -m project2.src.termos.termos gerar --gold project2/data/gold/casos.txt --saida project2/data/termos.csv
   python -m project2.src.termos.termos comparar --termos project2/data/termos.csv --saida project2/data/comparacao.csv --top 100
   python -m project2.src.termos.termos associar --saida project2/data/associacoes.csv
   ```

2. **Etapa 2 — Extração de Fronteiras de Menções (CRF):**
   ```bash
   python -m project2.src.entidades.entidades treinar
   python -m project2.src.entidades.entidades prever --saida project2/data/mencoes.csv
   ```

3. **Etapa 3 — Classificação de Tipos, Códigos MeSH e Polaridade (Cascata Léxico + LR):**
   ```bash
   python -m project2.src.tipos.tipos treinar
   python -m project2.src.tipos.tipos prever --entrada project2/data/mencoes.csv --saida project2/data/mencoes_tipadas.csv
   ```

4. **Etapa 4 — Classificação de Relações Clínicas (LR 1-2 N-grams):**
   ```bash
   python -m project2.src.relacoes.relacoes treinar
   python -m project2.src.relacoes.relacoes prever --mencoes project2/data/mencoes_tipadas.csv --saida project2/data/relacoes.csv
   ```

5. **Montagem do Grafo de Conhecimento e Visualizador:**
   ```bash
   python -m project2.src.montagem.montagem --mencoes project2/data/mencoes_tipadas.csv --relacoes project2/data/relacoes.csv --saida project2/data/grafo --visualizador project2/data/visualizador
   ```
   *Nota: O visualizador compila tanto os grafos do Projeto 2 quanto os do Projeto 1, disponibilizando abas para inspeção e auditoria comparativa direta.*

6. **Etapa 5 — Avaliação Completa contra o Gabarito:**
   ```bash
   python -m project2.src.avaliacao.avaliar --saida project2/data/resultados
   ```

Consulte [`src/README.md`](../src/README.md) para detalhes de instalação e dependências.
