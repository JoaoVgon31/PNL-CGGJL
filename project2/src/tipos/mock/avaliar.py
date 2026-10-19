"""Mock do avaliar.py da #29: tipagem de menções (cobertura, acurácia, P/R/F1 por tipo, confusão).

Cada menção predita é pareada a no máximo uma do gabarito, no mesmo caso: pelo mesmo início e
fim (`exato`) ou por qualquer interseção (`sobreposicao`). Tipo vazio = a menção ficou sem tipo.

    cobertura  = menções do gabarito pareadas e com algum tipo / menções do gabarito
    acuracia   = menções do gabarito pareadas com o tipo certo / menções do gabarito
    P(t)       = acertos de t / preditas como t (inclusive as que não casaram com o gabarito)
    R(t)       = acertos de t / t no gabarito
    macro F1   = média do F1 dos tipos que aparecem no gabarito
"""
from __future__ import annotations

from collections import Counter, defaultdict

SEM_TIPO = ""


def parear(pred: list[dict], gold: list[dict], exato: bool = True) -> list[tuple[dict | None, dict | None]]:
    """Pares (predita, gold) um para um; quem sobra vem com o outro lado None."""
    gold_caso = defaultdict(list)
    for g in gold:
        gold_caso[g["case_id"]].append(g)
    usados, pares = set(), []
    for p in sorted(pred, key=lambda m: (m["case_id"], m["start"], m["end"])):
        for g in gold_caso.get(p["case_id"], []):
            if id(g) in usados:
                continue
            if (g["start"], g["end"]) == (p["start"], p["end"]) if exato else (p["start"] < g["end"] and g["start"] < p["end"]):
                usados.add(id(g))
                pares.append((p, g))
                break
        else:
            pares.append((p, None))
    pares += [(None, g) for g in gold if id(g) not in usados]
    return pares


def avaliar_tipos(pred: list[dict], gold: list[dict], exato: bool = True) -> dict:
    """{cobertura, acuracia, macro_f1, n_gold, n_pred, por_tipo: {t: {precisao, revocacao, f1, n}}, confusao}."""
    pares = parear(pred, gold, exato)
    acertos, preditos, no_gold = Counter(), Counter(), Counter()
    confusao = Counter()
    for p, g in pares:
        tipo_p = p["tipo"] if p else SEM_TIPO
        if tipo_p != SEM_TIPO:
            preditos[tipo_p] += 1
        if g is None:
            continue
        no_gold[g["tipo"]] += 1
        confusao[(g["tipo"], tipo_p)] += 1
        if tipo_p == g["tipo"]:
            acertos[tipo_p] += 1

    por_tipo = {}
    for tipo in sorted(no_gold):
        p = acertos[tipo] / preditos[tipo] if preditos[tipo] else 0.0
        r = acertos[tipo] / no_gold[tipo]
        por_tipo[tipo] = {"precisao": p, "revocacao": r, "f1": 2 * p * r / (p + r) if p + r else 0.0,
                          "n": no_gold[tipo]}
    n_gold = sum(no_gold.values())
    tipados = sum(v for (_, tp), v in confusao.items() if tp != SEM_TIPO)
    return {"cobertura": tipados / n_gold if n_gold else 0.0,
            "acuracia": sum(acertos.values()) / n_gold if n_gold else 0.0,
            "macro_f1": sum(m["f1"] for m in por_tipo.values()) / len(por_tipo) if por_tipo else 0.0,
            "n_gold": n_gold, "n_pred": len(pred), "por_tipo": por_tipo, "confusao": dict(confusao)}
