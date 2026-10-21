# Experimento preliminar da Etapa 1 (histórico)

Registro de desenvolvimento, anterior ao gabarito final: 3 casos foram reservados como gabarito
provisório e os termos foram contados nos 53 restantes. Os números finais estão no
[README do projeto](../../README.md#resultados).

- `termos.csv`, `comparacao.csv` e os JSONs: ranking de 600 candidatos e cobertura MeSH do top-100
  (20 com correspondência exata), com parâmetros e hashes dos dados.
- `validacao_corpus.json` e `proveniencia_corpus.json`: leitura do Parquet completo (Zenodo 20416562,
  98.641 casos), na qual os 56 textos da amostra foram encontrados sem alteração.
- `validacao_tokenizador_antes.json` e `validacao_tokenizador_corpus.json`: tokenização do corpus
  completo antes e depois de o `_` ser tratado como pontuação (713 falhas passaram a zero).
