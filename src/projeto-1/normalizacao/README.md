# Normalização

Parser de casos clínicos baseado em regras clássicas de PNL. O componente lê
um caso de `cases.csv`, extrai entidades e relações, normaliza os rótulos e
exporta o grafo em tabelas CSV.

## Estrutura

- `core/`: modelos e construção do grafo;
- `normalizers/`: texto, siglas, unidades e medições;
- `extractors/`: entidades clínicas e relações;
- `exporters/`: CSV, relatório de impacto e Mermaid;
- `tests/`: suíte automatizada;
- `output/`: artefatos gerados para os casos processados;
- `pipeline.py`: orquestração do processamento;
- `main.py`: interface de linha de comando.

## Execução

A partir da raiz do repositório, entre no diretório que contém o pacote e
execute-o como módulo:

```powershell
Push-Location src/projeto-1
python -m normalizacao --cases ../../sample/cases.csv --case-id PMC5137649_01
Pop-Location
```

Por padrão, os arquivos são gravados em `src/projeto-1/normalizacao/output`.
Outro destino pode ser informado com `--output`.

## Testes

```powershell
python -m unittest discover `
  -s src/projeto-1/normalizacao/tests `
  -t src/projeto-1 `
  -p "test_*.py"
```
Mais informações em: [DOCS - Normalização](https://github.com/caiomelloni/PNL-CGGJL/blob/feat/issue-4-normalizacao/docs/projeto-1/04-normalizacao.md)
