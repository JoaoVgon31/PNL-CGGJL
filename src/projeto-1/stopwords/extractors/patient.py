"""Extração dos atributos da entidade Patient (um nó por caso)."""

import re
from typing import Any

from ..case_reader import ClinicalCase

_AGE_PATTERN = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)[\s-]*(?P<unit>year|month|week|day)s?[\s-]*(?:-?\s*old|of age)",
    re.IGNORECASE,
)

_GESTATIONAL_PATTERN = re.compile(
    r"(?P<value>\d+)\s*(?:\d/\d\s*)?weeks?\s+gestational\s+age",
    re.IGNORECASE,
)

_UNIT_MAP = {"year": "years", "month": "months", "week": "weeks", "day": "days"}


def extract_patient_attributes(case: ClinicalCase, text: str) -> dict[str, Any]:
    """Monta os atributos do nó Patient, preferindo a idade do texto à do CSV."""
    text_age, text_unit = _extract_age_from_text(text)

    attributes: dict[str, Any] = {
        "case_id": case.case_id,
        "article_id": case.article_id,
        "gender": case.gender or None,
    }

    if text_age is not None:
        attributes["age"] = text_age
        attributes["age_unit"] = text_unit
    elif case.age is not None:
        attributes["age"] = case.age
        attributes["age_unit"] = "years"

    return attributes


def _extract_age_from_text(text: str) -> tuple[str | None, str | None]:
    gestational_match = _GESTATIONAL_PATTERN.search(text)
    if gestational_match is not None:
        return gestational_match.group("value"), "weeks_gestational"

    age_match = _AGE_PATTERN.search(text)
    if age_match is not None:
        unit = _UNIT_MAP[age_match.group("unit").lower()]
        return age_match.group("value"), unit

    return None, None
