# Gabarito manual

8 casos da amostra anotados à mão pelo grupo ([#29](https://github.com/caiomelloni/PNL-CGGJL/issues/29)),
seguindo o [guia de anotação](../../docs/guia-anotacao.md). Esses casos ficam fora de todo treino e
servem só para avaliação. Os ids estão em [`casos.txt`](casos.txt).

| Caso | Menções | Relações |
|---|---:|---:|
| `PMC11259348_01` | 16 | 15 |
| `PMC11723754_01` | 32 | 28 |
| `PMC3437073_01` | 52 | 40 |
| `PMC4630775_01` | 9 | 8 |
| `PMC6083636_03` | 20 | 19 |
| `PMC6949661_01` | 58 | 51 |
| `PMC9532611_01` | 15 | 13 |
| `PMC9969157_01` | 22 | 19 |
| **Total** | **224** | **193** |

## Arquivos

- `mencoes.csv`: `case_id, id, start, end, texto, tipo, mesh, polaridade`. Offsets de caractere
  em `[start, end)` sobre o `case_text`, com `texto == case_text[start:end]`. `polaridade` é
  `present` ou `absent`.
- `relacoes.csv`: `case_id, origem, destino, relacao`. `origem` é `P1` para relações do paciente ou o
  `id` de uma menção.
- `cases/<case_id>/`: texto do caso e as planilhas de anotação por caso
  (`-entities.csv`, `-relations.csv`). `src/relacoes/avaliar_gabarito.py` ainda lê essas planilhas.

Os módulos de avaliação ([`src/avaliacao`](../../src/avaliacao/)) leem `mencoes.csv` e `relacoes.csv`.
