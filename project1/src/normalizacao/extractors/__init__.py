"""Extratores de entidades e relações clínicas."""

from .common import ExtractedEntity
from .history import extract_history
from .patient import extract_patient
from .symptoms import extract_symptoms

__all__ = [
    "ExtractedEntity",
    "extract_history",
    "extract_patient",
    "extract_symptoms",
]
