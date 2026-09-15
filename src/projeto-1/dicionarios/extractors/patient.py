from __future__ import annotations

from case_reader import ClinicalCase
from core.graph import GraphBuilder
from core.models import Node


def extract_patient(case: ClinicalCase, graph: GraphBuilder) -> Node:
    return graph.add_node(
        "Patient",
        f"case {case.case_id}",
        {
            "article_id": case.article_id,
            "age": case.age or None,
            "age_unit": "years" if case.age else None,
            "gender": case.gender or None,
        },
    )
