# Comum — texto e corpus compartilhados

Todas as etapas devem usar o mesmo `case_text`, tokenizador e divisor de frases. Os offsets são
índices de caracteres Python, no intervalo semiaberto `[start, end)`, incluindo a contagem de espaços.
Não são offsets em bytes. O leitor não normaliza nem remove caracteres do texto.

## API

Execute os exemplos a partir da raiz do repositório:

```python
from project2.src.comum import (
    REPO, ler_casos, iter_casos, iter_registros,
    tokenizar, dividir_frases, etiquetar, casos_gold,
)

casos = ler_casos(limite=2)  # lista de (case_id, case_text), por padrão os 56 casos do P1
for case_id, texto in iter_casos("project2/data/corpus/csv/full/cases.csv", limite=100):
    pass  # lê um caso de cada vez; limite é aplicado antes da exclusão do gold

for registro in iter_registros("project1/data/case_texts.csv", limite=1):
    print(registro["case_id"], registro["case_text"])
    # age, gender e article_id também são preservados quando constam na entrada

texto = "She had nausea."
tokens = tokenizar(texto)
assert texto[tokens[2].start:tokens[2].end] == "nausea"
classes = etiquetar(tokens)  # HMM já treinado em project1/src/sintagmas/model/hmm_pos.json
for frase in dividir_frases(texto):
    assert texto[frase.start:frase.end] == frase.text

reservados = casos_gold("project2/data/mock/gold/casos.txt")  # só demonstração
treino = [(c, t) for c, t in casos if c not in reservados]
```

| Função | Retorno e validação |
|---|---|
| `ler_casos(caminho=CASOS_PADRAO, limite=None)` | Lista de tuplas; materializa os textos |
| `iter_casos(caminho=CASOS_PADRAO, limite=None)` | Iterador de tuplas; preferir no corpus completo |
| `iter_registros(caminho=CASOS_PADRAO, limite=None)` | Iterador de dicionários com todos os campos disponíveis |
| `tokenizar(texto)` | Tokens P1 com `text`, `start`, `end`, `index`, `kind` |
| `dividir_frases(texto)` | Frases P1 com `text`, `start`, `end`, `index` |
| `etiquetar(tokens)` | Uma classe universal por token; aceita sublistas com índices globais |
| `casos_gold(caminho=GOLD_PADRAO)` | Conjunto de ids; arquivo ausente, vazio ou inválido causa erro |

CSV exige `case_id,case_text`, aceita UTF-8 com BOM e campos multilinha, e rejeita ids duplicados.
Limite zero não lê casos; limite negativo é erro. Linhas vazias e comentários `#` são ignorados na
lista gold. Seu caminho padrão é `project2/data/gold/casos.txt`, nunca o mock automaticamente.

`tokenizar` reutiliza `ClinicalRegexTokenizer`; `dividir_frases` reutiliza `split_sentences`.
O contrato de frases permanece igual ao P1: exclui pontuação terminal e conserva espaços iniciais.
O divisor preserva decimais como `3.5`, mas ainda é simples e pode separar abreviações com ponto.
O adaptador HMM conserva as restrições de unidades/referências a figuras e os reparos do P1.

## Coletar o corpus completo

A coleta segue a fonte e o desaninhamento do
[tutorial do professor](https://github.com/santanche/nlp2learn/blob/main/to-kg/notebooks/01_data_preparation.ipynb).
Baixa apenas `cases.parquet`, `metadata.parquet` e `data_dictionary.csv`, sem as imagens.

```bash
python3 -m pip install -r project2/src/comum/requirements.txt
python3 -m project2.src.comum.coletar
# Para repetir uma versão específica, use o ID registrado no manifesto:
python3 -m project2.src.comum.coletar --registro 20416562
```

O diretório padrão é `project2/data/corpus/`. Contém `raw/<record_id>/`, `csv/full/` com os três CSVs
e `proveniencia.json`. Resolvem-se as versões pela API Zenodo `versions/latest`; tamanho e MD5 são
conferidos antes de reutilizar arquivos. Downloads incompletos têm sufixo `.part` e são retomados
por HTTP Range, com até 3 tentativas e conferência final de checksum. Se o servidor ignorar Range,
reinicia-se a transferência em vez de concatenar arquivos incorretamente. O número de casos
vem dos arquivos efetivamente obtidos; não é fixado em “93 mil”. O volume depende da versão; o
tutorial registra aproximadamente 190 MB nos Parquet, além do espaço da exportação em CSV.
O progresso é impresso durante a transferência. O tempo depende da conexão; não há estimativa
validada para todas as máquinas.

Ao contrário do notebook completo da disciplina, este utilitário exporta somente o corpus completo:
não gera um banco DuckDB persistente nem uma nova amostra aleatória. Os 56 textos já versionados
continuam sendo a amostra de desenvolvimento. A leitura também aceita Parquet diretamente, plano
ou com a coluna `cases` aninhada por artigo; para isso instale DuckDB com o requirements acima.

## Validação no corpus

O leitor foi executado nos **98.641 casos** do `cases.parquet` do registro Zenodo `20416562`,
versão `3.0.1`, após validar tamanho e MD5. Todos os 56 casos da amostra foram encontrados com
`case_text` exatamente igual ao recorte do P1. Ver [registro da verificação](../../experimentos/amostra/validacao_corpus.json).
Essa verificação testa leitura/compatibilidade de texto; não é uma execução de termos no corpus inteiro.

A tokenização foi conferida também nos 98.641 casos: **51.804.708 tokens, zero falhas**, em cerca
de 93 segundos nesta máquina. O regex original falhava em 713 casos com `_` isolado; a alternativa
de pontuação passou a aceitar esse caractere, sem alterar o ranking gerado nos 56 casos conhecidos.
Os registros [antes](../../experimentos/amostra/validacao_tokenizador_antes.json) e
[depois](../../experimentos/amostra/validacao_tokenizador_corpus.json) preservam a verificação.
Essa passagem não executa o HMM nem a contagem de termos no corpus inteiro.

## Integrar com as etapas 2 e 3

Na etapa 2, o import compartilhado passa a ser:

```python
from project2.src.comum import REPO, casos_gold, dividir_frases, etiquetar, ler_casos, tokenizar
from project2.src.termos.termos import ler_termos
```

Ao executar um script diretamente, adicione a raiz do repositório ao `sys.path` antes desse import,
como nos scripts `termos.py` e `montagem.py`, ou execute com a raiz no `PYTHONPATH`.
Além dos imports, é preciso atualizar os caminhos do silver, do gold e de `termos.csv`.
Usar o leitor real mantendo caminhos de mocks não transforma o experimento em definitivo.
As funções `ler_casos`, `tokenizar`, `dividir_frases`, `etiquetar` e `casos_gold` mantêm as assinaturas
esperadas pelo mock da etapa 2. A lista oficial do gold continua sendo responsabilidade da #29.
