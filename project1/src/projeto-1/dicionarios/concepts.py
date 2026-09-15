from __future__ import annotations

from core.graph import GraphBuilder
from core.models import Node
from extractors.common import ExtractedEntity
from matching import link_label_to_concept


def link_entities_to_concepts(
    entities: list[ExtractedEntity],
    gazetteers: list[dict[str, list[tuple[str, str]]]],
    graph: GraphBuilder,
    concept_nodes: dict[str, Node],
    vocabulary: str = "MeSH",
) -> None:
    for entity in entities:
        match = None
        for gazetteer in gazetteers:
            match = link_label_to_concept(entity.node.label, gazetteer)
            if match is not None:
                break

        if match is None:
            continue

        if match.code not in concept_nodes:
            concept_nodes[match.code] = graph.add_node(
                "Concept",
                match.preferred_term,
                {
                    "vocabulary": vocabulary,
                    "code": match.code,
                    "preferred_term": match.preferred_term,
                },
            )

        graph.add_edge(
            entity.node,
            concept_nodes[match.code],
            "SAME_AS",
            {"strategy": match.strategy, "score": match.score},
        )
