"""Descoberta e expansão de siglas definidas dentro de um caso clínico."""

import re
from collections.abc import Mapping


_ACRONYM_IN_PARENTHESES = re.compile(
    r"\((?P<short_form>[A-Z][A-Z0-9-]{1,9})\)"
)

_SENTENCE_BOUNDARY = re.compile(r"[.!?;:\n\r]")


def _select_long_form(short_form: str, candidate: str) -> str | None:
    """Encontra, no fim do candidato, a expansão correspondente à sigla.

    O casamento é feito de trás para frente. Assim, EUS pode corresponder a
    "endoscopic ultrasound": S e U são encontrados em "ultrasound", enquanto
    E é encontrado no início de "endoscopic".
    """
    short_characters = [
        character.lower()
        for character in short_form
        if character.isalnum()
    ]

    if len(short_characters) < 2:
        return None

    long_index = len(candidate) - 1

    for short_index in range(len(short_characters) - 1, -1, -1):
        expected = short_characters[short_index]

        while long_index >= 0:
            current = candidate[long_index].lower()
            is_word_start = (
                long_index == 0
                or not candidate[long_index - 1].isalnum()
            )

            if current == expected and (
                short_index != 0 or is_word_start
            ):
                break

            long_index -= 1

        if long_index < 0:
            return None

        long_index -= 1

    long_form = candidate[long_index + 1:].strip(" \t,–—-")

    if not long_form:
        return None

    word_count = len(long_form.split())
    maximum_words = min(
        len(short_characters) + 5,
        len(short_characters) * 2,
    )

    if word_count > maximum_words:
        return None

    return long_form


def discover_acronyms(case_text: str) -> dict[str, str]:
    """Descobre relações ``SIGLA -> forma extensa`` dentro de um caso."""
    if not isinstance(case_text, str):
        raise TypeError("case_text must be a string")

    definitions: dict[str, str] = {}

    for match in _ACRONYM_IN_PARENTHESES.finditer(case_text):
        short_form = match.group("short_form")

        context_start = max(0, match.start() - 200)
        preceding_context = case_text[context_start:match.start()]
        candidate = _SENTENCE_BOUNDARY.split(preceding_context)[-1].strip()

        long_form = _select_long_form(short_form, candidate)

        if long_form is not None:
            # Mantemos a primeira definição encontrada no caso. Se uma mesma
            # sigla tiver dois significados, isso deverá ser auditado depois.
            definitions.setdefault(short_form, long_form)

    return definitions


def expand_acronyms(
    text: str,
    definitions: Mapping[str, str],
) -> str:
    """Expande siglas usando somente as definições do caso atual."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    expanded = text

    # Siglas maiores devem ser processadas primeiro para evitar conflitos.
    ordered_definitions = sorted(
        definitions.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    )

    for short_form, long_form in ordered_definitions:
        # "computed tomography (CT)" vira apenas "computed tomography".
        complete_definition = re.compile(
            rf"{re.escape(long_form)}\s*"
            rf"\(\s*{re.escape(short_form)}\s*\)"
        )
        expanded = complete_definition.sub(long_form, expanded)

        # Também funciona em "CT demonstrated..." e "EUS-guided".
        isolated_acronym = re.compile(
            rf"(?<![A-Za-z0-9])"
            rf"{re.escape(short_form)}"
            rf"(?![A-Za-z0-9])"
        )
        expanded = isolated_acronym.sub(long_form, expanded)

    return expanded