"""Mock do avaliar.py da #29: P, R e F1 de menções, com casamento exato e por sobreposição."""
from __future__ import annotations

from collections import defaultdict

Span = tuple[str, int, int]  # (case_id, start, end)


def _por_caso(spans: list[Span]) -> dict[str, list[tuple[int, int]]]:
    agrupados = defaultdict(list)
    for case_id, inicio, fim in spans:
        agrupados[case_id].append((inicio, fim))
    return agrupados


def _casados(pred: list[Span], gold: list[Span], exato: bool) -> int:
    """Pares um para um: cada menção do gabarito casa com no máximo uma predita."""
    total = 0
    gold_caso = _por_caso(gold)
    for case_id, preditos in _por_caso(pred).items():
        livres = sorted(set(gold_caso.get(case_id, [])))
        for inicio, fim in sorted(set(preditos)):
            for k, (g_ini, g_fim) in enumerate(livres):
                if ((g_ini, g_fim) == (inicio, fim)) if exato else (inicio < g_fim and g_ini < fim):
                    total += 1
                    del livres[k]
                    break
    return total


def avaliar_mencoes(pred: list[Span], gold: list[Span]) -> dict[str, dict[str, float]]:
    """{'exato'|'sobreposicao': {precisao, revocacao, f1, n_pred, n_gold, casados}}."""
    n_pred, n_gold = len(set(pred)), len(set(gold))
    saida = {}
    for modo, exato in (("exato", True), ("sobreposicao", False)):
        casados = _casados(pred, gold, exato)
        p = casados / n_pred if n_pred else 0.0
        r = casados / n_gold if n_gold else 0.0
        saida[modo] = {"precisao": p, "revocacao": r, "f1": 2 * p * r / (p + r) if p + r else 0.0,
                       "n_pred": n_pred, "n_gold": n_gold, "casados": casados}
    return saida
