# Tipos — o tipo clínico de cada entidade (léxico + regressão logística)

Etapa 3 do projeto 2. Recebe a tabela de menções da etapa 2 (`case_id, id, start, end, texto`) e
completa cada linha com `tipo` e `mesh`. Os dicionários do projeto 1 resolvem o que conhecem; uma
regressão logística com TF-IDF de N-gramas dá o tipo ao resto. O código `mesh` vem sempre dos
dicionários.

## Dependências

```bash
pip install -r project2/src/tipos/requirements.txt
python -c "import nltk; nltk.download('punkt_tab')"
```

Todos os comandos rodam da raiz do repositório.

## Gerar tudo, na ordem

Nada abaixo é versionado (ver `.gitignore`); cada passo recria seus arquivos.

| # | Comando | Gera | Tempo |
|---|---|---|---|
| 1 | `python project2/src/dados/silver.py` | silver e regras (`data/silver/mencoes.csv`, `data/regras/mencoes.csv`) | ~5 s |
| 2 | `python project2/src/tipos/tipos.py treinar` | `models/tipos/classificador.pkl` | ~10 s |
| 3 | `python project2/src/tipos/tipos.py tipar [--modo M] [--entrada CSV]` | `data/mencoes_tipadas.csv` | ~5 s |
| 4 | `python project2/src/tipos/tipos.py comparar` | refaz 2 e grava `data/resultados/tipos.csv`, `tipos_confusao.csv` e `tipos_por_mencao.csv` | ~15 s |

Para reproduzir a comparação do zero bastam os passos 1 e 4. A linha ponta a ponta do passo 4
precisa também das menções do CRF (`entidades.py treinar` e `entidades.py prever`); sem elas, só
as fronteiras do gabarito e as regras P1 são avaliadas. `tipos.py resumo` mostra as menções por tipo
no silver e no gabarito.

Testes: `python -m unittest discover -s project2/src/tipos/tests`.

## Saídas

- `data/mencoes_tipadas.csv` — `case_id, id, start, end, texto, tipo, mesh, polaridade, confianca, fonte`;
  `fonte` é `lexico`, `classificador` ou vazio (sem tipo); o léxico responde com confiança 1;
  `polaridade` é `present` ou `absent` (pelo detector de negação na oração do Projeto 1).
- `data/resultados/tipos.csv` — `sistema, entrada, casamento, cobertura, acuracia, macro_f1,
  acuracia_polaridade, f1_absent, n_pred, n_gold` e o F1 de cada tipo (`regras P1` + 4 modos nas
  fronteiras do `gabarito` e nas menções do `crf`).
- `data/resultados/tipos_confusao.csv` — `(gold, previsto) → n` de cada sistema.
- `data/resultados/tipos_por_mencao.csv` — cada menção do gabarito com o tipo de cada sistema.

Cobertura é a fração das menções do gabarito que recebeu algum tipo; acurácia, a que recebeu o tipo
certo (sem tipo conta como erro).

## Sistemas comparados (`--modo`)

| Modo | Quem dá o tipo |
|---|---|
| `regras P1` | linha de base das regras do Projeto 1 (`data/regras/mencoes.csv`) |
| `lexico` | só os dicionários (com expansão de siglas definidas no próprio texto) |
| `lexico+classificador` (padrão) | os dicionários; o classificador tipa o que eles não conhecem |
| `ambiguas` | como o anterior, mas o classificador decide também quando o tipo veio de `diseases` ou `drugs` do MeSH |
| `classificador` | só o classificador |

`diseases` e `drugs` são ambíguas: a primeira inclui sinais e sintomas (`nausea` é D009325), e a
segunda é a árvore D inteira do MeSH, com os analitos dos exames (`hemoglobin`, `glucose`). No modo
`ambiguas`, se o classificador fica abaixo do limiar, o tipo dos dicionários é mantido.

## Léxico (`lexico.py`) e Expansão de Siglas

Três dicionários, do mais confiável para o menos: os `TERMS` do `pos_bio.py`, o gazetteer de
`AnatomicalSite` e o MeSH, com o tipo vindo da categoria (`drugs` → Medication, `diseases` e
`mental_disorders` → Diagnosis, `treatments` → Treatment, `exams` → Exam). Dentro da menção vale o
maior trecho de até 6 palavras que algum dicionário conhece; no empate, o dicionário mais confiável e
depois o trecho mais à direita (o núcleo do sintagma). Sem casamento aproximado, e todo trecho precisa
de uma palavra com 3 letras ou mais (o MeSH tem sinônimos como `AT 10`). Quando o próprio texto define
uma sigla entre parênteses (`Transesophageal echocardiogram (TEE)`), as ocorrências da sigla no mesmo
caso herdam o tipo e o código MeSH da forma extensa.

## Pistas e treino

Cada menção vira o texto dela e as 3 palavras de cada lado, marcadas pelo lado (`E:with`, `D:and`).
Daí saem três TF-IDF: N-gramas de 2 a 5 caracteres da menção (sufixos como `-itis` e `-ectomy`,
unidades), palavras e pares de palavras da menção, e palavras do contexto. O modelo é a
`LogisticRegression` do scikit-learn; `C` e o peso das classes saem de uma grade 4 × 2 pelo macro F1
em 1 de cada 5 casos do silver, e o limiar de confiança pelo F1 micro no mesmo conjunto. Abaixo do
limiar a menção fica sem tipo.

O treino usa o tipo que as regras do projeto 1 inteiras deram (o silver), nunca os casos do gabarito.
As menções `Medication` do silver são limpas antes: a regra de dose do projeto 1 pega as 3 palavras
antes da dose (`a dose of 5 mg`, `BUN 17 mg`), então a menção fica só com o nome do remédio
(`Rifampin 600 mg` → `Rifampin`) e sai quando não há remédio conhecido.

## Integração

Esta etapa consome diretamente:
- `project2/src/comum/` (#32) para leitura dos casos e lista do gabarito.
- `project2/src/dados/silver.py` (#29) para `data/silver/mencoes.csv` e `data/regras/mencoes.csv`.
- `project2/src/avaliacao/avaliar.py` (#29) para métricas de tipagem e polaridade contra `data/gold/mencoes.csv`.
