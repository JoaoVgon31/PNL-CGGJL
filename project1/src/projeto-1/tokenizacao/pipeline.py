"""Orquestração do caso clínico até o grafo."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from case_reader import read_case
from extraction import ExtractionResult, extract_case
from graph import GraphBuilder
from models import ClinicalCase, Token
from tokenizers import BaseTokenizer, get_tokenizer


@dataclass(frozen=True)
class PipelineResult:
    case: ClinicalCase
    tokenizer_name: str
    tokens: tuple[Token, ...]
    graph: GraphBuilder
    extraction: ExtractionResult


def process_case(case: ClinicalCase, tokenizer: BaseTokenizer) -> PipelineResult:
    tokens = tokenizer.tokenize(case.case_text)
    graph = GraphBuilder(case.case_id)
    extraction = extract_case(case, tokens, graph)
    return PipelineResult(
        case=case,
        tokenizer_name=tokenizer.name,
        tokens=tuple(tokens),
        graph=graph,
        extraction=extraction,
    )


def process_case_from_csv(
    csv_path: str | Path,
    case_id: str,
    tokenizer_name: str = "clinical_regex",
) -> PipelineResult:
    return process_case(read_case(csv_path, case_id), get_tokenizer(tokenizer_name))
