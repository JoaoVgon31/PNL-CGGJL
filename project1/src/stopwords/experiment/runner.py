"""Roda as 4 condições x 3 listas sobre um conjunto de casos."""

from dataclasses import dataclass

from ..case_reader import read_case
from ..pipeline import process_case
from .conditions import Condition, WORDLISTS
from .diff import CaseDiff, diff_graphs

_NON_BASELINE_CONDITIONS = (
    Condition.NAIVE_UNPROTECTED,
    Condition.GUARDED_GLOBAL,
    Condition.GUARDED_LABEL,
)


@dataclass(frozen=True)
class VariantResult:
    """O diff de uma condição x lista específica, para um caso."""

    condition: Condition
    wordlist: str
    diff: CaseDiff


def run_case(csv_path: str, case_id: str) -> list[VariantResult]:
    """Roda BASELINE + as 9 combinações (condição x lista) para um caso."""
    case = read_case(csv_path, case_id)
    baseline_result = process_case(case, Condition.BASELINE)

    results = []
    for condition in _NON_BASELINE_CONDITIONS:
        for wordlist in WORDLISTS:
            variant_result = process_case(case, condition, wordlist)
            diff = diff_graphs(baseline_result.graph, variant_result.graph)
            results.append(VariantResult(condition=condition, wordlist=wordlist, diff=diff))

    return results


def run_experiment(csv_path: str, case_ids: list[str]) -> list[VariantResult]:
    """Roda run_case para cada case_id e concatena os resultados."""
    all_results = []
    for case_id in case_ids:
        all_results.extend(run_case(csv_path, case_id))
    return all_results
