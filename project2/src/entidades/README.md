# Entidades — onde cada entidade começa e termina (CRF)

Etapa 2 do projeto 2 (#33). Marca cada palavra do caso como `B` (começa uma entidade), `I`
(continua) ou `O` (fora), sem tipo — quem tipa é a etapa 3. Um CRF aprende essa marcação a
partir do silver (as regras do projeto 1 rodadas nos casos) e é comparado com as próprias regras.

## Dependências

```bash
pip install -r project2/src/entidades/requirements.txt
python -c "import nltk; nltk.download('punkt_tab')"   # exigido pelo combinado.py do projeto 1
```

O texto dos casos vem de `project1/data/case_texts.csv` (versionado). Todos os comandos rodam da
raiz do repositório.

## Gerar tudo, na ordem

Nada abaixo é versionado (ver `.gitignore`); cada passo recria seus arquivos.

| # | Comando | Gera | Tempo |
|---|---|---|---|
| 1 | `python project2/src/dados/silver.py && python project2/src/termos/termos.py gerar` | `data/silver/mencoes.csv`, `data/regras/mencoes.csv`, `data/termos.csv` | ~10 s |
| 2 | `python project2/src/entidades/entidades.py treinar` | `models/entidades/crf.pkl` | ~20 s |
| 3 | `python project2/src/entidades/entidades.py treinar --termos` | `models/entidades/crf_termos.pkl` | ~20 s |
| 4 | `python project2/src/entidades/entidades.py prever [--termos] [--todos]` | `data/mencoes.csv` (casos do gabarito; `--todos` para os 56) | ~5 s |
| 5 | `python project2/src/entidades/entidades.py comparar` | refaz 2–4 e grava `data/resultados/entidades.csv` e `data/resultados/entidades_por_sistema.csv` | ~45 s |

Para reproduzir a comparação do zero bastam os passos 1 e 5. No passo 5, `mencoes.csv` sai da
variante (com ou sem termos) que teve o melhor F1 na validação do silver — nunca escolhida pelo
gabarito. `entidades_por_sistema.csv` traz as menções de cada sistema lado a lado, para inspeção.

Testes: `python -m unittest discover -s project2/src/entidades/tests`.

## Saídas

- `data/mencoes.csv` — `case_id, id, start, end, texto`; `texto == case_text[start:end]`.
- `data/resultados/entidades.csv` — `sistema, casamento, precisao, revocacao, f1, n_pred, n_gold, casados`;
  4 sistemas (regras P1, só `pos_bio`, CRF, CRF + termos) × 2 casamentos (exato: mesmo início e fim;
  sobreposição: qualquer interseção, um para um).

## Pistas de cada palavra

Palavra em minúsculas; prefixos e sufixos de 1 a 3 letras; maiúscula, título, dígito, hífen;
formato colapsado (`CA19-9` → `Xd-d`); classe gramatical do HMM do `pos_bio.py`; palavra e classe
das 2 vizinhas de cada lado (ou marca de início/fim de frase); e, com `--termos`, se a palavra está
em um termo do `termos.csv` (`B`/`I`/`O`, casamento mais longo). O CRF é o `lbfgs` do
`sklearn-crfsuite`; `c1` e `c2` saem de uma grade 3 × 3 avaliada em 1 de cada 5 casos do silver.

Do silver para o BIO: um token entra no span se tiver interseção com ele; spans sobrepostos
(sítio anatômico dentro de um sintoma) ficam só com o mais longo, porque o BIO é plano. A mesma
regra é aplicada às saídas das regras e do `pos_bio` antes de avaliar.

## Integração

Esta etapa consome diretamente os módulos oficiais:
- `project2/src/comum/` (#32) para leitura dos casos, tokenização (`ClinicalRegexTokenizer`), divisão em frases (`split_sentences`) e POS tagging (`HMMTagger`).
- `project2/src/termos/termos.py` (#32) para leitura do vocabulário de termos compostos (`project2/data/termos.csv`).
- `project2/src/dados/silver.py` (#29) para o silver standard (`project2/data/silver/mencoes.csv`) e linha de base das regras (`project2/data/regras/mencoes.csv`).
- `project2/src/avaliacao/avaliar.py` (#29) para cálculo de precisão, revocação e F1 (`exato` e `sobreposicao`) contra `project2/data/gold/mencoes.csv`.
