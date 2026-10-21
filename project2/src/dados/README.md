# Dados — Geração do Silver Standard e Linha de Base das Regras (#29)

Executa o extrator em lote do Projeto 1 (`combinado.py`) sobre os casos clínicos para gerar:

1. **Silver Standard (`project2/data/silver/`)**: dados de treino por supervisão fraca nos casos fora de `project2/data/gold/casos.txt`.
2. **Linha de Base das Regras (`project2/data/regras/`)**: extrações das regras do Projeto 1 exclusivamente sobre os casos reservados do gabarito (`project2/data/gold/casos.txt`), para comparação direta com os modelos do Projeto 2.

## Execução

Da raiz do repositório:

```bash
python project2/src/dados/silver.py
```

Parâmetros opcionais:
- `--casos CAMINHO`: CSV ou Parquet de casos (padrão: `project1/data/case_texts.csv`).
- `--gold CAMINHO`: lista de `case_id` reservados para avaliação (padrão: `project2/data/gold/casos.txt`).
- `--saida PASTA`: diretório de saída (padrão: `project2/data`).
- `--limite N`: processa apenas os `N` primeiros casos.

## Arquivos Gerados

- `project2/data/silver/mencoes.csv` e `project2/data/regras/mencoes.csv`:
  - Colunas: `case_id,id,start,end,texto,tipo,mesh,polaridade`
  - `texto == case_text[start:end]` (alinhamento exato de caracteres).
- `project2/data/silver/relacoes.csv` e `project2/data/regras/relacoes.csv`:
  - Colunas: `case_id,origem,destino,relacao`
  - Relações do Projeto 1 ancoradas nas menções por sobreposição de offsets `[char_start, char_end]` + tipo clínico + proximidade do gatilho (`trigger`). Quando a origem é o paciente, `origem = P1`.
- `project2/data/silver/bio.conll`:
  - Formato: `token\tpos\tbio_fronteira\tbio_tipo`, com uma linha em branco separando cada sentença.
