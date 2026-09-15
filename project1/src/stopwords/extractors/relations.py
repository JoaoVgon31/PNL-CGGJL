"""Monta as 12 arestas do esquema a partir das entidades já extraídas."""

from ..core.graph import GraphBuilder
from ..core.models import Node
from .common import Mention

_DIRECT_PATIENT_RELATIONS = {
    "Symptom": "HAS_SYMPTOM",
    "History": "HAS_HISTORY",
    "Exam": "UNDERWENT_EXAM",
    "Diagnosis": "DIAGNOSED_WITH",
    "Outcome": "HAS_OUTCOME",
}

_REVEAL_TRIGGERS = ("demonstrat", "reveal", "showed", "noted")
_SUPPORT_TRIGGERS = ("suggesting", "after having", "based on", "consistent with")
_CERTAINTY_RANK = {"confirmed": 3, "probable": 2, "suspected": 1, "excluded": 0}

_MentionNodePairs = dict[str, list[tuple[Mention, Node]]]


def _edge_attributes(mention: Mention) -> dict:
    return {
        "evidence_text": mention.sentence.text.strip(),
        "trigger": mention.trigger,
        "certainty": "hedged" if mention.hedged else "asserted",
        "char_start": mention.char_start,
        "char_end": mention.char_end,
    }


def build_relations(graph: GraphBuilder, patient_id: str, mentions: _MentionNodePairs) -> None:
    """Adiciona ao grafo as 12 arestas do esquema, uma vez por entidade extraída."""
    for node_type, relation in _DIRECT_PATIENT_RELATIONS.items():
        for mention, node in mentions.get(node_type, []):
            graph.add_edge(patient_id, node.node_id, relation, _edge_attributes(mention))

    _build_result_edges(graph, mentions)
    _build_finding_edges(graph, patient_id, mentions)
    _build_support_edges(graph, mentions)
    _build_treatment_edges(graph, patient_id, mentions)
    _build_location_edges(graph, mentions)
    _build_revision_edges(graph, mentions)


def _build_result_edges(graph: GraphBuilder, mentions: _MentionNodePairs) -> None:
    exams = mentions.get("Exam", [])
    for mention, node in mentions.get("ExamResult", []):
        exam_match = next(
            (exam_node for exam_mention, exam_node in exams
             if exam_mention.sentence.index == mention.sentence.index),
            None,
        )
        if exam_match is not None:
            graph.add_edge(exam_match.node_id, node.node_id, "HAS_RESULT", _edge_attributes(mention))


def _build_finding_edges(graph: GraphBuilder, patient_id: str, mentions: _MentionNodePairs) -> None:
    sources = mentions.get("Exam", []) + mentions.get("Treatment", [])
    for mention, node in mentions.get("Finding", []):
        lowered = mention.sentence.text.lower()
        has_reveal_verb = any(trigger in lowered for trigger in _REVEAL_TRIGGERS)
        source_match = next(
            (source_node for source_mention, source_node in sources
             if source_mention.sentence.index == mention.sentence.index),
            None,
        )
        if has_reveal_verb and source_match is not None:
            graph.add_edge(source_match.node_id, node.node_id, "REVEALS", _edge_attributes(mention))
        else:
            graph.add_edge(patient_id, node.node_id, "HAS_FINDING", _edge_attributes(mention))


def _build_support_edges(graph: GraphBuilder, mentions: _MentionNodePairs) -> None:
    diagnoses = mentions.get("Diagnosis", [])
    for node_type in ("Symptom", "Finding", "ExamResult", "History"):
        for mention, node in mentions.get(node_type, []):
            lowered = mention.sentence.text.lower()
            if not any(trigger in lowered for trigger in _SUPPORT_TRIGGERS):
                continue
            diagnosis_match = next(
                (diag_node for diag_mention, diag_node in diagnoses
                 if abs(diag_mention.sentence.index - mention.sentence.index) <= 1),
                None,
            )
            if diagnosis_match is not None:
                graph.add_edge(node.node_id, diagnosis_match.node_id, "SUPPORTS", _edge_attributes(mention))


def _build_treatment_edges(graph: GraphBuilder, patient_id: str, mentions: _MentionNodePairs) -> None:
    diagnoses = mentions.get("Diagnosis", [])
    for node_type in ("Treatment", "Medication"):
        for mention, node in mentions.get(node_type, []):
            diagnosis_match = next(
                (diag_node for diag_mention, diag_node in diagnoses
                 if diag_mention.sentence.index <= mention.sentence.index
                 and mention.sentence.index - diag_mention.sentence.index <= 2),
                None,
            )
            source_id = diagnosis_match.node_id if diagnosis_match is not None else patient_id
            graph.add_edge(source_id, node.node_id, "TREATED_WITH", _edge_attributes(mention))


def _build_location_edges(graph: GraphBuilder, mentions: _MentionNodePairs) -> None:
    for mention, node in mentions.get("AnatomicalSite", []):
        for node_type in ("Symptom", "Finding", "Treatment"):
            for source_mention, source_node in mentions.get(node_type, []):
                if source_mention.sentence.index == mention.sentence.index:
                    graph.add_edge(source_node.node_id, node.node_id, "LOCATED_IN", _edge_attributes(mention))


def _build_revision_edges(graph: GraphBuilder, mentions: _MentionNodePairs) -> None:
    diagnoses = sorted(mentions.get("Diagnosis", []), key=lambda pair: pair[0].sentence.index)
    for earlier_index, (earlier_mention, earlier_node) in enumerate(diagnoses):
        for later_mention, later_node in diagnoses[earlier_index + 1:]:
            if later_node.label == earlier_node.label:
                continue
            earlier_rank = _CERTAINTY_RANK.get(earlier_mention.attributes.get("certainty"), 3)
            later_rank = _CERTAINTY_RANK.get(later_mention.attributes.get("certainty"), 3)
            if later_rank > earlier_rank:
                graph.add_edge(later_node.node_id, earlier_node.node_id, "REVISES", _edge_attributes(later_mention))
