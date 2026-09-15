"""Comparação reproduzível dos tokenizadores e do impacto no grafo."""

from __future__ import annotations

from collections import Counter

from case_reader import iter_cases
from models import ClinicalCase
from pipeline import process_case
from tokenizers import TOKENIZERS, BaseTokenizer


CHALLENGES = {
    "number_and_glued_unit": (
        "12,476.5ng/ml",
        ["12,476.5", "ng/ml"],
    ),
    "multidimensional_size": (
        "6cm x 9cm",
        ["6", "cm", "x", "9", "cm"],
    ),
    "glued_slash_unit": (
        "6iu/ml",
        ["6", "iu/ml"],
    ),
    "hyphenated_acronym": (
        "EUS-FNA",
        ["EUS-FNA"],
    ),
    "hyphenated_term": (
        "contrast-enhanced",
        ["contrast-enhanced"],
    ),
    "exam_with_numeric_hyphen": (
        "CA 19-9",
        ["CA", "19-9"],
    ),
    "figure_reference": (
        "(Fig 1)",
        ["(Fig 1)"],
    ),
    "reference_range": (
        "10-140 U/L",
        ["10-140", "U/L"],
    ),
    "slash_compound": (
        "body/tail",
        ["body/tail"],
    ),
}


def evaluate_challenges(tokenizer: BaseTokenizer) -> dict[str, object]:
    results: dict[str, object] = {}
    passed = 0
    for name, (text, expected) in CHALLENGES.items():
        tokens = tokenizer.tokenize(text)
        actual = [token.text for token in tokens]
        offsets_valid = all(text[token.start:token.end] == token.text for token in tokens)
        success = actual == expected and offsets_valid
        passed += int(success)
        results[name] = {
            "input": text,
            "expected": expected,
            "actual": actual,
            "offsets_valid": offsets_valid,
            "passed": success,
        }
    return {"passed": passed, "total": len(CHALLENGES), "details": results}


def _graph_metrics(case: ClinicalCase, tokenizer: BaseTokenizer) -> dict[str, object]:
    result = process_case(case, tokenizer)
    node_types = Counter(node.type for node in result.graph.nodes)
    relations = Counter(edge.relation for edge in result.graph.edges)
    return {
        "token_count": len(result.tokens),
        "node_count": len(result.graph.nodes),
        "edge_count": len(result.graph.edges),
        "nodes_by_type": dict(sorted(node_types.items())),
        "edges_by_relation": dict(sorted(relations.items())),
    }


def compare_case(case: ClinicalCase) -> dict[str, object]:
    report: dict[str, object] = {"case_id": case.case_id, "tokenizers": {}}
    tokenizers = report["tokenizers"]
    assert isinstance(tokenizers, dict)
    for name, tokenizer_class in TOKENIZERS.items():
        tokenizer = tokenizer_class()
        try:
            tokenizers[name] = {
                "challenges": evaluate_challenges(tokenizer),
                "graph": _graph_metrics(case, tokenizer),
            }
        except RuntimeError as error:
            tokenizers[name] = {"available": False, "error": str(error)}
    return report


def compare_sample(csv_path) -> dict[str, object]:
    cases = list(iter_cases(csv_path))
    report: dict[str, object] = {
        "case_count": len(cases),
        "tokenizers": {},
        "note": "Contagens medem rendimento estrutural, não precisão clínica.",
    }
    for name, tokenizer_class in TOKENIZERS.items():
        tokenizer = tokenizer_class()
        totals = Counter()
        node_types = Counter()
        relations = Counter()
        try:
            challenge_result = evaluate_challenges(tokenizer)
            for case in cases:
                result = process_case(case, tokenizer)
                totals["tokens"] += len(result.tokens)
                totals["nodes"] += len(result.graph.nodes)
                totals["edges"] += len(result.graph.edges)
                node_types.update(node.type for node in result.graph.nodes)
                relations.update(edge.relation for edge in result.graph.edges)
            report["tokenizers"][name] = {
                "available": True,
                "challenges_passed": challenge_result["passed"],
                "challenges_total": challenge_result["total"],
                "offset_invariant": True,
                "totals": dict(totals),
                "nodes_by_type": dict(sorted(node_types.items())),
                "edges_by_relation": dict(sorted(relations.items())),
            }
        except RuntimeError as error:
            report["tokenizers"][name] = {"available": False, "error": str(error)}
    return report
