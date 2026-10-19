# Etapa 1 — termos compostos e integração do grafo

## Problema e hipótese

Nomes clínicos compostos podem ser quebrados ou parcialmente reconhecidos pelas regras do projeto 1.
A hipótese desta etapa é que frequências, associação entre palavras e estrutura nominal forneçam
candidatos úteis, inclusive ausentes do gazetteer. A etapa 2 testa se a lista ajuda o CRF a delimitar
entidades, comparando o modelo com e sem a pista de termos.

## Metodologia

O módulo comum fixa os textos, tokens, frases e offsets para toda a equipe. Os mesmos algoritmos
do P1 são reutilizados. Os casos reservados para avaliação são excluídos antes da contagem.

Contam-se N-gramas de 1 a 4 palavras, sem cruzar sentenças ou pontuação. Candidatos compostos
precisam atingir a frequência mínima e ter ao menos metade das ocorrências com POS nominal
`(ADJ|NOUN)* NOUN`, segundo o HMM do P1. Contagens são acumuladas em SQLite para limitar a memória
usada por sequências raras do corpus completo.

O PMI usa frequências de bigramas e marginais posicionais no mesmo universo. Para candidatos de
3/4 palavras, registra-se o menor PMI dos pares adjacentes.
O C-value considera tamanho e frequência, descontando a média das frequências dos candidatos
maiores que contêm o termo. O ranking prioriza C-value e usa PMI e frequência como desempates.
Os detalhes e as fórmulas estão no [README do módulo](../src/termos/README.md).

Compara-se o ranking ao MeSH por correspondência lexical exata normalizada, preservando códigos
ambíguos. Essa comparação mede cobertura do dicionário, não a correção clínica dos candidatos.

## Experimento preliminar

Entrada: `project1/data/case_texts.csv`, com 56 casos. Exclusão: os 3 casos do **gabarito mock** da
etapa 2. Parâmetros: frequência mínima 2 e N máximo 4. Não é o gold definitivo da #29.

| Medida | Valor |
|---|---:|
| Casos processados | 53 |
| Casos mock reservados excluídos | 3 |
| Ocorrências de unigramas | 25.535 |
| Ocorrências de bigramas | 21.174 |
| Ocorrências de trigramas | 17.903 |
| Ocorrências de quadrigramas | 15.100 |
| Candidatos compostos após filtros | 600 |
| Termos conhecidos pelo MeSH entre os 100 primeiros | 20 |
| Candidatos sem correspondência exata entre os 100 primeiros | 80 |

Arquivos: [ranking](../experimentos/amostra/termos.csv), [comparação](../experimentos/amostra/comparacao.csv),
[parâmetros e tempo](../experimentos/amostra/termos.json), [resumo lexical](../experimentos/amostra/comparacao.json).

`physical examination`, `white blood cell count` e `abdominal pain` aparecem entre os primeiros
candidatos e têm correspondência MeSH. `computed tomography` não casa exatamente com os termos
do gazetteer usado, mostrando por que ausência lexical não implica novidade médica.
Há também ruído, como `s serum`, decorrente da segmentação de possessivos e dos erros POS.
Os 80 candidatos desconhecidos não são apresentados como descobertas clínicas confirmadas.

Não foi medido ganho de F1: isso exige a integração com o CRF e avaliação independente. As regras
P1 foram ajustadas olhando a amostra, e o mock não substitui os casos externos exigidos pela #29.
O experimento definitivo deve repetir a contagem no corpus completo, com a lista gold oficial,
e avaliar o CRF com/sem termos nos mesmos casos reservados.

## Cobertura de processamento no corpus completo

A coleta do registro Zenodo 20416562 (v3.0.1) produziu 98.641 casos, com tamanho/MD5 dos três
arquivos de origem verificados. Os 56 textos da amostra foram encontrados sem alterações.
Uma passagem de tokenização revelou 713 casos em que o regex P1 rejeitava `_` isolado, pois esse
caractere não entrava nem como palavra nem como pontuação. Foi acrescentada sua classificação
como pontuação. A nova passagem produziu 51.804.708 tokens nos 98.641 casos, sem falhas.
O ranking dos 53 casos de desenvolvimento permaneceu idêntico. Os registros estão na pasta
[do experimento](../experimentos/amostra/). Essa cobertura mede funcionamento/offsets do
tokenizador, não qualidade clínica nem o resultado da extração estatística no corpus inteiro.

## Montagem do grafo

As menções tipadas e relações são convertidas para os CSVs do P1. Menções do mesmo tipo e polaridade
são agrupadas por rótulo normalizado ou código; medidas são atributos; códigos geram nós `Concept`
e arestas `SAME_AS`. Preservam-se textos e spans de origem. Negação não é apagada pela fusão de nós.
A saída pode ser exportada para uma cópia do visualizador P1. A integração final depende das
tabelas reais das etapas 3/4; a demonstração sintética só comprova o funcionamento do contrato.

## Referências

- Church, K. W.; Hanks, P. (1990). [Word Association Norms, Mutual Information, and Lexicography](https://aclanthology.org/J90-1003/).
- Frantzi, K.; Ananiadou, S.; Mima, H. (2000). [Automatic recognition of multi-word terms: the C-value/NC-value method](https://research.manchester.ac.uk/en/publications/automatic-recognition-of-multi-word-terms-the-c-valuenc-value-met/).
- Santanchè, A. [Projeto 2](https://github.com/santanche/nlp2learn/tree/main/projects/2026/project2) e [preparação dos dados](https://github.com/santanche/nlp2learn/blob/main/to-kg/notebooks/01_data_preparation.ipynb).
