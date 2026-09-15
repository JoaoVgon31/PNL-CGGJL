"""Criação das relações do grafo a partir das entidades extraídas."""

import re
from dataclasses import dataclass

from ..core.graph import GraphBuilder
from ..core.models import Edge, Node
from .common import ExtractedEntity
from .exams import ExtractedExamResult
from .findings import ExtractedFinding


@dataclass(frozen=True)
class ExtractedCaseEntities:
    """Todas as entidades extraídas de um caso clínico."""

    patient: Node
    symptoms: tuple[ExtractedEntity, ...] = ()
    histories: tuple[ExtractedEntity, ...] = ()
    exams: tuple[ExtractedEntity, ...] = ()
    exam_results: tuple[ExtractedExamResult, ...] = ()
    findings: tuple[ExtractedFinding, ...] = ()
    diagnoses: tuple[ExtractedEntity, ...] = ()
    medications: tuple[ExtractedEntity, ...] = ()
    treatments: tuple[ExtractedEntity, ...] = ()
    outcomes: tuple[ExtractedEntity, ...] = ()


def _edge_attributes(
    evidence_text: str,
    trigger: str,
    start: int,
    end: int,
    *,
    certainty: str = "asserted",
) -> dict[str, object]:
    return {
        "evidence_text": evidence_text,
        "trigger": trigger,
        "certainty": certainty,
        "char_start": start,
        "char_end": end,
    }


def _add_unique_edge(
    graph: GraphBuilder,
    source: Node,
    target: Node,
    relation: str,
    attributes: dict[str, object],
) -> Edge:
    """Evita repetir a mesma relação entre o mesmo par de nós."""
    for edge in graph.edges:
        if (
            edge.source_id == source.node_id
            and edge.target_id == target.node_id
            and edge.relation == relation
        ):
            return edge

    return graph.add_edge(
        source.node_id,
        target.node_id,
        relation,
        attributes,
    )


def _overlap(first_start: int, first_end: int, second_start: int, second_end: int) -> bool:
    return first_start < second_end and second_start < first_end


def _direct_patient_edges(
    graph: GraphBuilder,
    patient: Node,
    entities: tuple[ExtractedEntity, ...],
    relation: str,
) -> None:
    for entity in entities:
        certainty = (
            "hedged"
            if entity.node.attributes.get("certainty") in {"suspected", "probable"}
            else "asserted"
        )
        _add_unique_edge(
            graph,
            patient,
            entity.node,
            relation,
            _edge_attributes(
                entity.evidence_text,
                entity.trigger,
                entity.char_start,
                entity.char_end,
                certainty=certainty,
            ),
        )


def _add_exam_relations(graph: GraphBuilder, entities: ExtractedCaseEntities) -> None:
    exam_evidence = {item.node.node_id: item for item in entities.exams}
    for result in entities.exam_results:
        exam_evidence.setdefault(
            result.exam_node.node_id,
            ExtractedEntity(
                result.exam_node,
                result.evidence_text,
                "laboratory result",
                result.char_start,
                result.char_end,
            ),
        )
        _add_unique_edge(
            graph,
            result.exam_node,
            result.node,
            "HAS_RESULT",
            _edge_attributes(
                result.evidence_text,
                "result",
                result.char_start,
                result.char_end,
            ),
        )

    for item in exam_evidence.values():
        _add_unique_edge(
            graph,
            entities.patient,
            item.node,
            "UNDERWENT_EXAM",
            _edge_attributes(item.evidence_text, item.trigger, item.char_start, item.char_end),
        )


def _add_finding_relations(graph: GraphBuilder, entities: ExtractedCaseEntities) -> None:
    producers: list[ExtractedEntity] = list(entities.exams) + list(entities.treatments)
    for finding in entities.findings:
        item = finding.entity
        same_sentence = [
            producer for producer in producers
            if _overlap(item.char_start, item.char_end, producer.char_start, producer.char_end)
        ]
        if same_sentence and item.node.attributes.get("source") != "physical_exam":
            producer = same_sentence[-1]
            _add_unique_edge(
                graph,
                producer.node,
                item.node,
                "REVEALS",
                _edge_attributes(item.evidence_text, item.trigger, item.char_start, item.char_end),
            )
        else:
            _add_unique_edge(
                graph,
                entities.patient,
                item.node,
                "HAS_FINDING",
                _edge_attributes(item.evidence_text, item.trigger, item.char_start, item.char_end),
            )

        for site in finding.anatomical_sites:
            _add_unique_edge(
                graph,
                item.node,
                site,
                "LOCATED_IN",
                _edge_attributes(item.evidence_text, "located in", item.char_start, item.char_end),
            )


def _add_treatment_relations(graph: GraphBuilder, entities: ExtractedCaseEntities) -> None:
    for item in (*entities.treatments, *entities.medications):
        _add_unique_edge(
            graph,
            entities.patient,
            item.node,
            "TREATED_WITH",
            _edge_attributes(item.evidence_text, item.trigger, item.char_start, item.char_end),
        )


def _add_support_relations(graph: GraphBuilder, entities: ExtractedCaseEntities) -> None:
    evidence: list[tuple[Node, int, int, str]] = []
    evidence.extend((item.node, item.char_start, item.char_end, item.evidence_text) for item in entities.symptoms)
    evidence.extend((item.node, item.char_start, item.char_end, item.evidence_text) for item in entities.histories)
    evidence.extend((item.entity.node, item.entity.char_start, item.entity.char_end, item.entity.evidence_text) for item in entities.findings)
    evidence.extend((item.node, item.char_start, item.char_end, item.evidence_text) for item in entities.exam_results)

    for diagnosis in entities.diagnoses:
        context_start = max(0, diagnosis.char_start - 200)
        context = graph.case_text[context_start:diagnosis.char_end]
        marker = re.search(r"\b(?:based on|after having|suggesting|consistent with)\b", context, re.I)
        if marker is None:
            continue

        preceding = [item for item in evidence if item[2] <= diagnosis.char_end and item[0] != diagnosis.node]
        if not preceding:
            continue
        source, start, end, evidence_text = min(
            preceding,
            key=lambda item: abs(diagnosis.char_start - item[2]),
        )
        _add_unique_edge(
            graph,
            source,
            diagnosis.node,
            "SUPPORTS",
            _edge_attributes(
                evidence_text,
                marker.group(0),
                start,
                end,
                certainty="hedged" if diagnosis.node.attributes.get("certainty") == "suspected" else "asserted",
            ),
        )


def _add_revision_relations(graph: GraphBuilder, entities: ExtractedCaseEntities) -> None:
    pending: ExtractedEntity | None = None
    for diagnosis in sorted(entities.diagnoses, key=lambda item: item.char_start):
        certainty = diagnosis.node.attributes.get("certainty")
        if certainty in {"suspected", "probable"}:
            pending = diagnosis
        elif certainty == "confirmed" and pending is not None and pending.node is not diagnosis.node:
            _add_unique_edge(
                graph,
                pending.node,
                diagnosis.node,
                "REVISES",
                _edge_attributes(
                    diagnosis.evidence_text,
                    diagnosis.trigger,
                    diagnosis.char_start,
                    diagnosis.char_end,
                ),
            )
            pending = None


def build_relations(graph: GraphBuilder, entities: ExtractedCaseEntities) -> list[Edge]:
    """Cria todas as relações justificadas pelas entidades extraídas."""
    _direct_patient_edges(graph, entities.patient, entities.symptoms, "HAS_SYMPTOM")
    _direct_patient_edges(graph, entities.patient, entities.histories, "HAS_HISTORY")
    _direct_patient_edges(graph, entities.patient, entities.diagnoses, "DIAGNOSED_WITH")
    _direct_patient_edges(graph, entities.patient, entities.outcomes, "HAS_OUTCOME")
    _add_exam_relations(graph, entities)
    _add_finding_relations(graph, entities)
    _add_treatment_relations(graph, entities)
    _add_support_relations(graph, entities)
    _add_revision_relations(graph, entities)
    return graph.edges
