from __future__ import annotations

from nltk.tokenize import TreebankWordTokenizer

from core.graph import GraphBuilder

from .common import ExtractedEntity
from matching import match_text

_tokenizer = TreebankWordTokenizer()


def _tokenize_with_spans(text: str) -> tuple[list[str], list[tuple[int, int]]]:
    spans = list(_tokenizer.span_tokenize(text))
    tokens = [text[start:end] for start, end in spans]
    return tokens, spans


def _overlaps(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    return a_start < b_end and b_start < a_end


def extract_anatomical_sites(
    case_text: str,
    graph: GraphBuilder,
    gazetteer: dict[str, list[tuple[str, str]]],
    diagnosis_entities: list[ExtractedEntity],
    anchor_entities: list[ExtractedEntity],
) -> list[ExtractedEntity]:
    tokens, spans = _tokenize_with_spans(case_text)
    matches = match_text(tokens, gazetteer)

    extracted: list[ExtractedEntity] = []
    seen_spans: set[tuple[int, int]] = set()

    for match in matches:
        char_start = spans[match.start][0]
        char_end = spans[match.end - 1][1]

        if (char_start, char_end) in seen_spans:
            continue

        if any(
            _overlaps(char_start, char_end, d.char_start, d.char_end)
            for d in diagnosis_entities
        ):
            continue

        anchor = next(
            (
                a for a in anchor_entities
                if _overlaps(char_start, char_end, a.char_start, a.char_end)
            ),
            None,
        )
        if anchor is None:
            continue

        seen_spans.add((char_start, char_end))

        label = case_text[char_start:char_end]
        node = graph.add_node("AnatomicalSite", label, {})
        entity = ExtractedEntity(
            node=node,
            evidence_text=label,
            trigger="gazetteer",
            char_start=char_start,
            char_end=char_end,
        )
        graph.add_edge(anchor.node, node, "LOCATED_IN", {"evidence_text": label})
        extracted.append(entity)

    return extracted
