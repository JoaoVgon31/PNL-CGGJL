# Montagem do grafo

Este diretório reúne duas entregas. O comando `montagem.py`, descrito abaixo, é da #32.
Os módulos `data/`, `evaluation/` e `assembly/` vieram da #29 e estão descritos no
[README da etapa 5](README-etapa5.md). As duas rotas de montagem têm contratos e métodos de
agrupamento diferentes; a integração final ainda precisa definir qual será usada na avaliação.

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

Abra `http://localhost:8000`. A aba “Combinado” mostra o grafo P2; os arquivos originais do site
P1 são copiados sem alterações. O site publicado do projeto 1 permanece independente.
Também funciona `python3 project2/src/montagem/montagem.py ...`.

Todos os caminhos podem ser informados com `--mencoes`, `--relacoes`, `--corpus`, `--saida` e
`--visualizador`. Saída padrão: `project2/data/grafo/<case_id>-nodes.csv` e `-edges.csv`, mais `resumo.json`.
Na coluna `attributes`, pares simples mantêm o formato legado `chave=valor; chave=valor`.
Se um valor contiver uma sequência ambígua como `; p=`, o escritor usa um objeto JSON com
valores string. Os leitores `read_nodes_csv` e `read_edges_csv` de `project1.tools.graph_csv`
aceitam os dois formatos; use-os em vez de dividir a coluna manualmente por `;`.
CSV antigo escrito sem essa proteção precisa ser regenerado a partir da fonte para recuperar
o texto com segurança; a ambiguidade não pode ser resolvida apenas pela leitura.
O comando sem seleção inclui só casos presentes nas tabelas; `--gold` inclui também casos sem extrações.
Diretórios podem manter CSVs de execuções antigas; a exportação do visualizador usa somente os casos
selecionados na execução atual, conforme seu manifesto.

## Compatibilidade com o PR #38

Essa versão da etapa 3 ainda pode omitir a coluna `polaridade` e deixar menções sem `tipo`.
Até o contrato definitivo ser integrado, há opções explícitas:

```bash
python3 -m project2.src.montagem.montagem --polaridade-regras --ignorar-sem-tipo
```

`--polaridade-regras` completa apenas valores ausentes com `detect_polarity` do P1 na sentença
que contém a menção. Essa regra tem escopo de sentença e pode negar menções fora do alcance real
da negação. Valores já preenchidos são preservados. `--ignorar-sem-tipo` omite somente menções
cujo tipo é vazio e suas relações. O resumo registra quantas menções/relações foram omitidas e
quantas polaridades foram completadas. Sem as opções, essas incompatibilidades causam erro.

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
