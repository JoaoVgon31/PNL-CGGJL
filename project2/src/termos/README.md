# Termos compostos — N-gramas, PMI e C-value

Etapa 1, issue #32. Descobre candidatos a termos clínicos para fornecer a pista de fronteiras ao
CRF da etapa 2. Não exige modelo supervisionado nem usa o silver: aprende contagens nos textos,
excluindo os casos do gabarito. Usa o HMM e o tokenizador já existentes no P1.

## Dependências e execução

Python 3.10+ e biblioteca padrão para entradas CSV. Para Parquet, instale
`project2/src/comum/requirements.txt`. Não é necessário baixar modelos NLTK para o HMM versionado.

Da raiz do repositório, primeiro execute a demonstração na amostra:

```bash
python3 -m project2.src.termos.termos gerar --gold project2/data/mock/gold/casos.txt --saida project2/data/demo/termos.csv
python3 -m project2.src.termos.termos comparar --termos project2/data/demo/termos.csv --saida project2/data/demo/comparacao.csv --top 100
```

Para a entrega definitiva, obtenha a lista gold da #29 e colete o corpus conforme o README do comum:

```bash
python3 -m project2.src.termos.termos gerar --corpus project2/data/corpus/csv/full/cases.csv --freq-min 5 --n-max 4
python3 -m project2.src.termos.termos comparar --top 100
```

Também funciona `python3 project2/src/termos/termos.py gerar ...`.

| Parâmetro de `gerar` | Padrão | Significado |
|---|---|---|
| `--corpus` | `project1/data/case_texts.csv` | CSV ou Parquet dos casos |
| `--gold` | `project2/data/gold/casos.txt` | Exclusão obrigatória dos casos reservados |
| `--saida` | `project2/data/termos.csv` | Ranking a gerar |
| `--freq-min` | `2` | Número mínimo de ocorrências, não de documentos |
| `--n-max` | `4` | Maior N contado; aceita 2, 3 ou 4 |
| `--limite` | todos | Limite de casos lidos, antes de excluir gold |
| `--banco` | SQLite temporário | Caminho novo para preservar contagens; não sobrescreve bancos existentes |

`comparar` aceita `--termos`, `--gazetteer`, `--saida` e `--top`.
Cada CSV de saída tem um JSON acompanhante com parâmetros e resultados. A geração registra
hashes do corpus, lista gold, código e modelo HMM; a comparação registra hashes do ranking e do gazetteer.
O manifesto especifica se a execução foi limitada. A ordem é determinística; tempo de execução varia.

## Algoritmo

1. Lê um caso de cada vez e exclui os ids da lista gold antes de extrair contagens.
2. Tokeniza e etiqueta pelo módulo comum; conta N-gramas de 1 a N, sem atravessar frases,
   pontuação, números ou unidades. Palavras com hífen/barra preservadas pelo tokenizador podem participar.
3. Conserva candidatos de 2 a N palavras com frequência mínima e pelo menos metade das
   ocorrências compatível com `(ADJ|NOUN)* NOUN`. Essa é uma escolha explícita para POS ambíguo.
4. Calcula PMI de cada par adjacente sobre o mesmo universo de bigramas. Com B pares observados,
   `PMI(x,y) = log2(f(x,y) * B / (f_esquerda(x) * f_direita(y)))`.
   As marginais contam as posições esquerda/direita, evitando misturar universos de unigramas e bigramas.
5. Para um termo com 3/4 palavras, a coluna `pmi` é o **menor PMI dos pares adjacentes**, uma
   extensão conservadora escolhida nesta implementação. Não é a fórmula de PMI multivariado.
6. Calcula `C-value(a) = log2(len(a)) * f(a)` quando não aninhado; caso contrário, substitui
   `f(a)` por `f(a) - média(f(b))`, onde b são os candidatos maiores que contêm a como subtrecho contíguo.
   Cada termo maior conta uma vez, mesmo que repita o subtermo. O conjunto de candidatos vai só até N.
7. Ordena por C-value, PMI e frequência decrescentes, com desempate alfabético.

SQLite guarda todas as contagens em disco; só contagens do caso atual e candidatos já filtrados
são mantidos na memória. O C-value usa um índice de subtermos, evitando a comparação quadrática
de todos os candidatos. O espaço em disco e o tempo crescem com o vocabulário observado.

## Colunas e integração

| Coluna | Significado |
|---|---|
| `termo` | Palavras em minúsculas separadas por um espaço |
| `n` | Número de palavras, de 2 a N |
| `frequencia` | Ocorrências do termo nos casos processados |
| `pmi` | PMI do bigrama ou menor PMI adjacente do termo maior |
| `c_value` | Pontuação que desconta dependência de candidatos maiores |

Os unigramas são contados, com totais no JSON, mas o ranking contém somente termos compostos.

```python
from project2.src.termos.termos import ler_termos
termos = set(ler_termos("project2/data/termos.csv", limite=500))
# {("abdominal", "pain"), ...}, formato esperado pelo marcador BIO de termos do CRF
```

A comparação acrescenta `posicao`, `conhecido_mesh` (0/1) e `codigos_mesh` (todos os códigos,
separados por `|`, sem escolher arbitrariamente entre ambiguidades). Usa correspondência exata
após NFKC, casefold e compactação de espaços. Preserva números, unidades e pontuação:
`vitamin b` não corresponde a `Vitamin B 12`, nem `lactate dehydrogenase` à variante numerada `5`.
A filtragem de candidatos por tokens `WORD` é uma etapa separada e não é aplicada ao dicionário.
Não usa fuzzy match nem rótulos do gold. O JSON da comparação registra a política e o hash do código.

## Resultados e limites

A execução de desenvolvimento nos 53 casos restantes da amostra levou menos de 1 segundo para
gerar 600 candidatos com frequência mínima 2 nesta máquina; a comparação com o gazetteer levou
alguns segundos. Entre os 100 primeiros, 20 têm correspondência MeSH normalizada. Veja
[resultados reproduzíveis](../../experimentos/amostra/) e [discussão](../../docs/etapa-1.md).
Esses tempos não são medições do corpus completo.

Cobertura lexical não é precisão clínica: candidato novo pode ser termo útil, variante lexical ou
ruído. A avaliação do efeito sobre entidades vem do CRF com/sem termos no gold definitivo.
PMI favorece sequências raras; frequência mínima e C-value reduzem esse efeito, sem eliminá-lo.
Filtros POS ainda erram; abreviações e termos com preposições podem ser perdidos.

Referências: [Church e Hanks, 1990](https://aclanthology.org/J90-1003/);
[Frantzi, Ananiadou e Mima, 2000](https://research.manchester.ac.uk/en/publications/automatic-recognition-of-multi-word-terms-the-c-valuenc-value-met/).
