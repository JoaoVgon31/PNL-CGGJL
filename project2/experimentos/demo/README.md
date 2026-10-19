# Entradas sintéticas para demonstrar a montagem

`PMC0_01` é um identificador fictício. Texto, menções e relações foram criados para exercitar
o contrato entre tabelas, a extração de medidas, os códigos e a preservação da negação.
As confianças são ilustrativas. Estes arquivos não são dados MultiCaRe, gold ou resultados de modelo.

```bash
python3 -m project2.src.montagem.montagem --mencoes project2/experimentos/demo/mencoes.csv --relacoes project2/experimentos/demo/relacoes.csv --corpus project2/experimentos/demo/casos.csv --saida project2/data/demo/grafo --visualizador project2/data/demo/visualizador
python3 -m http.server 8000 --directory project2/data/demo/visualizador
```

O exemplo gera 10 nós (paciente, 5 entidades clínicas e 4 conceitos) e 10 arestas
(6 clínicas e 4 `SAME_AS`). A malignidade preserva `polarity=absent` e a medida vira `size`.
