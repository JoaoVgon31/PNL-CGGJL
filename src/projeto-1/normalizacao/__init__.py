"""Parser de casos clínicos baseado em normalização por regras."""

from .pipeline import PipelineResult, process_case, process_case_from_csv

__all__ = ["PipelineResult", "process_case", "process_case_from_csv"]
