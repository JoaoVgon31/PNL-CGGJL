from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET


CATEGORY_PREFIXES: dict[str, tuple[str, ...]] = {
    "diseases": ("C",),
    "drugs": ("D",),
    "exams": ("E01",),
    "treatments": ("E02", "E04"),
    "mental_disorders": ("F03",),
}

GAZETTEER_CSV_COLUMNS = ("term", "code", "preferred_term", "category")


@dataclass(frozen=True)
class MeshDescriptor:
    code: str
    preferred_term: str
    tree_numbers: tuple[str, ...]
    terms: tuple[str, ...]


def iter_descriptors(xml_path: str | Path):
    xml_path = Path(xml_path)
    context = ET.iterparse(str(xml_path), events=("end",))

    for _, elem in context:
        if elem.tag != "DescriptorRecord":
            continue

        code_elem = elem.find("DescriptorUI")
        name_elem = elem.find("DescriptorName/String")

        if code_elem is None or name_elem is None:
            elem.clear()
            continue

        code = code_elem.text.strip()
        preferred_term = name_elem.text.strip()

        tree_numbers = tuple(
            tn.text.strip()
            for tn in elem.findall("TreeNumberList/TreeNumber")
            if tn.text
        )

        terms_seen: list[str] = [preferred_term]
        for term_string in elem.findall("ConceptList/Concept/TermList/Term/String"):
            if term_string.text:
                term = term_string.text.strip()
                if term and term not in terms_seen:
                    terms_seen.append(term)

        yield MeshDescriptor(
            code=code,
            preferred_term=preferred_term,
            tree_numbers=tree_numbers,
            terms=tuple(terms_seen),
        )

        elem.clear()


def _matches_prefix(tree_numbers: tuple[str, ...], prefixes: tuple[str, ...]) -> bool:
    return any(tn.startswith(prefix) for tn in tree_numbers for prefix in prefixes)


def build_raw_gazetteer(
    xml_path: str | Path,
    tree_prefixes: tuple[str, ...] | None = None,
) -> dict[str, list[tuple[str, str]]]:
    gazetteer: dict[str, list[tuple[str, str]]] = defaultdict(list)

    for descriptor in iter_descriptors(xml_path):
        if tree_prefixes is not None and not _matches_prefix(
            descriptor.tree_numbers, tree_prefixes
        ):
            continue

        for term in descriptor.terms:
            entry = (descriptor.code, descriptor.preferred_term)
            if entry not in gazetteer[term]:
                gazetteer[term].append(entry)

    return dict(gazetteer)


def build_gazetteer_rows(
    xml_path: str | Path,
    category_prefixes: dict[str, tuple[str, ...]] = CATEGORY_PREFIXES,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    for descriptor in iter_descriptors(xml_path):
        matched_categories = [
            name
            for name, prefixes in category_prefixes.items()
            if _matches_prefix(descriptor.tree_numbers, prefixes)
        ]
        if not matched_categories:
            continue

        for category in matched_categories:
            for term in descriptor.terms:
                rows.append(
                    {
                        "term": term,
                        "code": descriptor.code,
                        "preferred_term": descriptor.preferred_term,
                        "category": category,
                    }
                )

    return rows


def save_gazetteer_csv(rows: list[dict[str, str]], csv_path: str | Path) -> None:
    csv_path = Path(csv_path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=GAZETTEER_CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def load_gazetteer_rows(csv_path: str | Path) -> list[dict[str, str]]:
    csv_path = Path(csv_path)

    with csv_path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def rows_to_raw_gazetteer(
    rows: list[dict[str, str]],
    category: str | None = None,
) -> dict[str, list[tuple[str, str]]]:
    gazetteer: dict[str, list[tuple[str, str]]] = defaultdict(list)

    for row in rows:
        if category is not None and row["category"] != category:
            continue

        entry = (row["code"], row["preferred_term"])
        if entry not in gazetteer[row["term"]]:
            gazetteer[row["term"]].append(entry)

    return dict(gazetteer)
