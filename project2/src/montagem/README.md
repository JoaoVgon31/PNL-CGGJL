# Montagem do grafo

Consome as saídas das etapas 3/4 e gera o mesmo contrato CSV do P1. Não treina modelos e não
cria relações clínicas por proximidade. Arestas do paciente devem vir da etapa 4 com `origem=P1`.
As únicas arestas adicionadas pela montagem são `SAME_AS`.

Python 3.10+, sem dependências adicionais para CSV. Execute da raiz do repositório.

## Entrada

- Menções: `case_id,id,start,end,texto,tipo,mesh,polaridade`; confiança e fonte opcionais.
- Relações: `case_id,origem,destino,relacao`; confiança e fonte opcionais.
- Corpus: `case_id,case_text`, com `age,gender,article_id` opcionais. Use o CSV completo
  para preservar metadados do paciente; o recorte `case_texts.csv` não contém esses metadados.

IDs de menção são locais ao caso; `P1` é reservado para o paciente. `NONE` não vira aresta.
Spans devem reproduzir o texto exato. Tipo, polaridade, domínio das relações, pontas e confiança
em [0,1] são validados; entrada inválida interrompe a montagem antes da gravação dos grafos.

## Comandos

Depois de as etapas 3/4 gerarem as entradas padrão:

```bash
# Um caso
python3 -m project2.src.montagem.montagem --case-id PMC5137649_01
# Todos os casos presentes nas tabelas
python3 -m project2.src.montagem.montagem
# Todos os casos do gold, incluindo os que ficaram sem menções
python3 -m project2.src.montagem.montagem --gold project2/data/gold/casos.txt --corpus project2/data/corpus/csv/full/cases.csv
# Exportar também uma cópia local do visualizador P1
python3 -m project2.src.montagem.montagem --visualizador project2/data/visualizador
python3 -m http.server 8000 --directory project2/data/visualizador
```

Abra `http://localhost:8000`. O visualizador exibe abas para alternar facilmente entre o grafo do **Projeto 1** e o do **Projeto 2** para cada caso clínico, facilitando a comparação direta entre as abordagens (regras vs. aprendizado de máquina). Por padrão, os grafos do Projeto 1 são obtidos de `project1/data/processed/` (configurável via `--p1-grafos`). Os arquivos do site P1 permanecem independentes.
Também funciona `python3 project2/src/montagem/montagem.py ...`.

Todos os caminhos podem ser informados com `--mencoes`, `--relacoes`, `--corpus`, `--saida` e
`--visualizador`. Saída padrão: `project2/data/grafo/<case_id>-nodes.csv` e `-edges.csv`, mais `resumo.json`.
A coluna `attributes` usa `chave=valor; chave=valor`, ou JSON quando algum valor contém algo como `; chave=`.
Leia-a com `read_nodes_csv`/`read_edges_csv` de `project1.tools.graph_csv`, não dividindo por `;`.
O comando sem seleção inclui só casos presentes nas tabelas; `--gold` inclui também casos sem extrações.
Diretórios podem manter CSVs de execuções antigas; a exportação do visualizador usa somente os casos
selecionados na execução atual, conforme seu manifesto.

## Entradas incompletas

Menção sem `tipo` ou sem `polaridade` interrompe a montagem. Duas opções relaxam isso:
`--ignorar-sem-tipo` omite essas menções e suas relações, e `--polaridade-regras` completa as
polaridades vazias com `detect_polarity` do P1 na frase da menção. O resumo registra o que foi
omitido ou completado.

## Desduplicação e rastreabilidade

- Agrupa por código ou rótulo normalizado, sempre dentro do mesmo caso, tipo e polaridade.
- Usa NFKC, minúsculas e compactação de espaços; medidas em cm/mm saem do rótulo e viram `size`.
  Reconhece faixas completas (`0.2-0.8 cm`, inclusive travessões e unidades nas duas pontas),
  dimensões com `x`/`×` e hífen entre valor e unidade (`7-mm`). Conserva a expressão em `size`,
  sem converter unidades nem descartar os limites de uma faixa.
- Mescla uma menção sem código com a de mesmo rótulo quando há um único código possível.
  Códigos conflitantes não são fundidos nem por intermédio de uma menção sem código.
- Não junta ocorrências presentes com negadas. Não realiza clustering por similaridade.
- Preserva ids de origem, textos e spans como atributos. Uma aresta clínica repetida guarda
  os pares de menções que a originaram; confiança é o máximo observado, não uma probabilidade recalibrada.
- A evidência exibida para a aresta cobre os spans das suas pontas (só a menção no caso de paciente).
  É contexto textual da relação recebida, não um gatilho inferido. Spans alternativos são preservados.
- Cria um único `Concept` por código no caso e uma `SAME_AS` por nó ligado.
- Não infere idade/gênero a partir do texto quando faltam metadados.

O agrupamento por rótulo/código segue a issue, mas ainda pode juntar duas lesões distintas com
o mesmo nome; não resolve correferência clínica. Os nós `Concept` usam o código como rótulo,
sem inventar um nome preferencial para códigos não consultados.

## Demonstração independente das outras etapas

As entradas pequenas em `project2/experimentos/demo/` são **sintéticas**, apenas para testar a montagem:

```bash
python3 -m project2.src.montagem.montagem --mencoes project2/experimentos/demo/mencoes.csv --relacoes project2/experimentos/demo/relacoes.csv --corpus project2/experimentos/demo/casos.csv --saida project2/data/demo/grafo --visualizador project2/data/demo/visualizador
```

O caso sintético não é parte do MultiCaRe, não é gabarito e não entra em qualquer métrica científica.
