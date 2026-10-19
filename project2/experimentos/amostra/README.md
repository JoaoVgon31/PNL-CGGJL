# Execução preliminar na amostra

Estes arquivos são resultados de desenvolvimento, **não do corpus completo nem do gold oficial**.
Os 3 casos do gabarito mock foram excluídos; restaram 53 casos para contar termos.

Reproduzir da raiz do repositório:

```bash
python3 -m project2.src.termos.termos gerar --gold project2/data/mock/gold/casos.txt --saida project2/experimentos/amostra/termos.csv
python3 -m project2.src.termos.termos comparar --termos project2/experimentos/amostra/termos.csv --saida project2/experimentos/amostra/comparacao.csv --top 100
```

`termos.csv` contém 600 candidatos; `comparacao.csv`, os 100 primeiros com correspondências MeSH.
Os JSONs registram os hashes dos dados e os parâmetros. O tempo pode variar entre execuções.
20/100 têm correspondência exata normalizada; os demais são candidatos a inspeção, não termos
clínicos confirmados. Ver [discussão](../../docs/etapa-1.md).

`validacao_corpus.json` registra uma verificação separada do leitor no Parquet completo
(registro Zenodo 20416562): 98.641 casos lidos, com os 56 textos da amostra encontrados sem alterações.
Essa validação não transforma o ranking acima em um ranking do corpus completo.

`proveniencia_corpus.json` copia o manifesto da coleta, com versão e checksums. Os arquivos
`validacao_tokenizador_antes.json` e `validacao_tokenizador_corpus.json` registram a cobertura do
tokenizador no corpus completo antes/depois da correção de `_`: 713 falhas passaram a zero.
Após a correção, foram produzidos 51.804.708 tokens. O SHA-256 do ranking da amostra permaneceu
`c388982597315fcfa9942a3f4a2c1f6a04c44268a10837a4e665c412838f137b`.
