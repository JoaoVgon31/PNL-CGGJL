# Código-fonte do Projeto 2 — instalação e execução

Cada etapa do pipeline fica em uma pasta própria, com um `README.md` detalhado:

| Pasta | Etapa | Issue |
|---|---|---|
| [`comum/`](comum/) | Leitura do corpus, tokens, frases e POS (HMM do projeto 1) compartilhados | [#32](https://github.com/caiomelloni/PNL-CGGJL/issues/32) |
| [`termos/`](termos/) | Etapa 1 — termos compostos por N-gramas (PMI, C-value) e associações MeSH | [#32](https://github.com/caiomelloni/PNL-CGGJL/issues/32) |
| [`entidades/`](entidades/) | Etapa 2 — fronteiras das menções com CRF | [#33](https://github.com/caiomelloni/PNL-CGGJL/issues/33) |
| [`tipos/`](tipos/) | Etapa 3 — tipo, conceito MeSH e polaridade | [#34](https://github.com/caiomelloni/PNL-CGGJL/issues/34) |
| [`relacoes/`](relacoes/) | Etapa 4 — relações (regra do paciente + classificador de N-gramas) | [#35](https://github.com/caiomelloni/PNL-CGGJL/issues/35) |
| [`dados/`](dados/) | Etapa 5 — corpus *silver* e linha de base das regras do projeto 1 | [#29](https://github.com/caiomelloni/PNL-CGGJL/issues/29) |
| [`avaliacao/`](avaliacao/) | Etapa 5 — métricas (menções, tipos, relações e grafo) | [#29](https://github.com/caiomelloni/PNL-CGGJL/issues/29) |
| [`montagem/`](montagem/) | Montagem dos grafos e exportação do visualizador | [#32](https://github.com/caiomelloni/PNL-CGGJL/issues/32) |

## Instalação

Python 3.10+. A partir da raiz do repositório:

~~~bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate   |   Windows: .venv\Scripts\activate
pip install -r project2/src/entidades/requirements.txt -r project2/src/tipos/requirements.txt -r project2/src/relacoes/requirements.txt
python -c "import nltk; nltk.download('punkt_tab')"
~~~

`project2/src/comum/requirements.txt` (`duckdb`) só é necessário para ler o corpus completo em Parquet.

## Execução (pipeline completo, a partir da raiz do repositório)

~~~bash
python -m project2.src.dados.silver                      # silver (casos não-gold) + linha de base P1 (casos gold)
python -m project2.src.termos.termos gerar               # Etapa 1: termos compostos
python -m project2.src.termos.termos comparar --top 100  #          cobertura MeSH do top-100
python -m project2.src.termos.termos associar            #          associações MeSH por PMI (diferencial)
python project2/src/entidades/entidades.py comparar      # Etapa 2: treina e avalia CRF / CRF + termos
python project2/src/entidades/entidades.py prever --todos
python project2/src/tipos/tipos.py comparar              # Etapa 3: avalia e treina o classificador
python project2/src/tipos/tipos.py tipar
python -m project2.src.relacoes.mock.gerar               # Etapa 4: pares de treino a partir do silver
python -m project2.src.relacoes.relacoes comparar        #          treina, avalia e gera data/relacoes.csv
python -m project2.src.montagem.montagem                 # grafos em project2/data/grafo/
python -m project2.src.montagem.montagem --visualizador project2/data/visualizador
python project2/src/avaliacao/avaliar.py consolidar      # tabelas comparativas P1 × P2
~~~

## Testes

~~~bash
python -m unittest discover -s project2/tests -v
python -m unittest discover -s project2/src/entidades/tests -v
python -m unittest discover -s project2/src/tipos/tests -v
python -m unittest discover -s project2/src/relacoes -v
~~~
