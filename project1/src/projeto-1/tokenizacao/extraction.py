"""Extração clínica rudimentar que consome uma sequência de tokens.

O objetivo deste módulo não é competir com um sistema clínico completo. Ele
mantém as outras estratégias simples para que seja possível trocar somente o
tokenizador e medir o efeito nos nós e arestas produzidos.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from graph import GraphBuilder
from models import ClinicalCase, Node, Token


@dataclass(frozen=True)
class Mention:
    node: Node
    start: int
    end: int
    sentence_start: int
    sentence_end: int
    trigger: str


@dataclass(frozen=True)
class ExtractionResult:
    patient: Node
    mentions: tuple[Mention, ...]


SYMPTOMS = (
    "lower quadrant abdominal pain", "abdominal distention", "abdominal pain",
    "epigastric pain", "flank pain", "weight loss", "night sweating",
    "constipation", "diarrhea", "vomiting", "emesis", "nausea", "fever",
    "headache", "dyspnea", "fatigue", "cough", "pain",
)

HISTORY_TERMS = (
    "type 2 diabetes mellitus", "diabetes mellitus", "hypertension", "asthma",
    "smoking", "tobacco", "alcohol",
)

EXAMS = {
    "contrast enhanced computed tomography": "imaging",
    "computed tomography": "imaging",
    "endoscopic ultrasound": "endoscopy",
    "oesophagogastroduodenoscopy": "endoscopy",
    "carcinoembryonic antigen": "laboratory",
    "carbohydrate antigen": "laboratory",
    "C-reactive protein": "laboratory",
    "Donath-Landsteiner test": "laboratory",
    "troponin I": "laboratory",
    "CA 19-9": "laboratory",
    "lipase": "laboratory",
    "pathology": "pathology",
    "biopsy": "pathology",
    "endoscopy": "endoscopy",
    "EUS-FNA": "endoscopy",
    "EUS": "endoscopy",
    "CT": "imaging",
}

FINDINGS = {
    "peripancreatic fat stranding": "imaging",
    "epigastric tenderness": "physical_exam",
    "cystic lesion": None,
    "solid mass": None,
    "mesenteric mass": "imaging",
    "adenocarcinoma": "pathology",
    "abnormalities": None,
    "lesion": None,
    "pseudocyst": None,
    "cyst": None,
    "mass": None,
}

DIAGNOSES = (
    "mucinous pancreatic cystic neoplasm", "gastric duplication cyst",
    "paroxysmal cold hemoglobinuria", "acute pancreatitis",
    "chronic pancreatitis", "pancreatic pseudocyst", "adenocarcinoma",
    "malignancy", "pancreatitis",
)

MEDICATIONS = (
    "moxifloxacin", "oseltamivir", "prednisone", "arbidol", "analgesia",
    "aspirin", "ibuprofen", "metformin", "insulin",
)

TREATMENTS = {
    "laparoscopic distal pancreatectomy": "surgery",
    "EUS-guided cystgastrostomy": "procedure",
    "laparoscopic gastrojejunostomy": "surgery",
    "blood transfusion": "transfusion",
    "open resection": "surgery",
    "surgical resection": "surgery",
    "intravenous fluids": "supportive",
    "chemotherapy": "procedure",
    "resection": "surgery",
}

ANATOMICAL_SITES = (
    "posterior wall of the stomach", "pancreatic tail", "lower quadrant",
    "coeliac axis", "mesenteric vessels", "duodenum", "pancreas", "stomach",
    "abdomen", "heart", "lung", "liver", "kidney", "body/tail",
)

OUTCOMES = {
    "discharged home": "discharge",
    "complete resolution": "resolution",
    "resolution of symptoms": "resolution",
    "no evidence of recurrence": "recurrence",
    "without any complications": "complication",
    "doing well": "improvement",
    "improved": "improvement",
    "expired": "death",
    "died": "death",
}

NEGATORS = {"no", "not", "without", "denied", "negative"}
DIAGNOSIS_TRIGGERS = (
    "diagnosed with", "diagnosis of", "consistent with", "suggesting",
    "final pathology", "revealed", "confirmed",
)
TREATMENT_TRIGGERS = (
    "treated with", "underwent", "performed", "planned", "started on",
    "received", "administered", "dose of", "therapy with",
)

_PATIENT_RE = re.compile(
    r"\b(?P<age>\d+(?:\.\d+)?)\s*[- ]\s*"
    r"(?P<unit>year|month|day)s?[- ]old\s+"
    r"(?P<gender>woman|man|female|male|girl|boy|patient)\b",
    re.IGNORECASE,
)
_GESTATIONAL_RE = re.compile(
    r"\bborn\s+at\s+(?P<whole>\d+)"
    r"(?:\s+(?P<num>\d+)/(?P<den>\d+))?\s+weeks?"
    r"(?:\s+of)?\s+gestational\s+age\b",
    re.IGNORECASE,
)
_DURATION_RE = re.compile(
    r"(?P<value>\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
    r"[- ](?P<unit>day|week|month|year)s?(?:\s+history\s+of)?\s*$",
    re.IGNORECASE,
)
_REFERENCE_RANGE_RE = re.compile(
    r"(?:normal|reference)\s+range\s*[:,]?\s*"
    r"(?P<low>\d+(?:\.\d+)?)\s*[-–—]\s*"
    r"(?P<high>\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


def _sentence_span(text: str, tokens: list[Token], position: int) -> tuple[int, int]:
    starts = [0]
    ends: list[int] = []
    for token in tokens:
        if token.kind == "PUNCTUATION" and token.text in ".!?":
            ends.append(token.end)
            starts.append(token.end)
    for newline in re.finditer(r"\n+", text):
        ends.append(newline.start())
        starts.append(newline.end())

    start = max((value for value in starts if value <= position), default=0)
    end = min((value for value in ends if value >= position), default=len(text))
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _edge_attributes(
    text: str,
    mention: Mention,
    *,
    certainty: str = "asserted",
) -> dict[str, object]:
    return {
        "evidence_text": text[mention.sentence_start:mention.sentence_end],
        "trigger": mention.trigger,
        "certainty": certainty,
        "char_start": mention.sentence_start,
        "char_end": mention.sentence_end,
    }


def _token_key(token: Token) -> str:
    return token.text.casefold()


def _find_phrases(tokens: list[Token], terms) -> list[tuple[str, int, int]]:
    """Retorna (termo, índice inicial, índice final exclusivo), sem sobrepor."""
    ordered = sorted(terms, key=lambda term: len(term.split()), reverse=True)
    occupied: set[int] = set()
    matches: list[tuple[str, int, int]] = []
    for term in ordered:
        parts = term.casefold().split()
        width = len(parts)
        for start in range(0, len(tokens) - width + 1):
            stop = start + width
            if any(index in occupied for index in range(start, stop)):
                continue
            if [_token_key(token) for token in tokens[start:stop]] == parts:
                matches.append((term, start, stop))
                occupied.update(range(start, stop))
    return sorted(matches, key=lambda match: match[1])


def _polarity(tokens: list[Token], start_index: int, sentence_start: int) -> str:
    preceding = [
        _token_key(token)
        for token in tokens[max(0, start_index - 5):start_index]
        if token.start >= sentence_start
    ]
    return "absent" if any(word in NEGATORS for word in preceding) else "present"


def _duration(text: str, mention_start: int, sentence_start: int) -> str | None:
    prefix = text[max(sentence_start, mention_start - 60):mention_start]
    match = _DURATION_RE.search(prefix)
    if match is None:
        return None
    value = match.group("value").casefold()
    unit = match.group("unit").casefold()
    suffix = "" if value in {"1", "one"} else "s"
    return f"{value} {unit}{suffix}"


def _extract_patient(case: ClinicalCase, graph: GraphBuilder) -> Node:
    age = case.age
    age_unit = None
    gender = case.gender or "Unknown"
    match = _PATIENT_RE.search(case.case_text)
    if match:
        age = Decimal(match.group("age"))
        age_unit = f"{match.group('unit').casefold()}s"
        gender_word = match.group("gender").casefold()
        if gender_word in {"woman", "female", "girl"}:
            gender = "Female"
        elif gender_word in {"man", "male", "boy"}:
            gender = "Male"
    else:
        gestational = _GESTATIONAL_RE.search(case.case_text)
        if gestational:
            age = Decimal(gestational.group("whole"))
            if gestational.group("num") and Decimal(gestational.group("den")) != 0:
                age += Decimal(gestational.group("num")) / Decimal(gestational.group("den"))
            age_unit = "weeks_gestational"
    return graph.add_node(
        "Patient",
        f"case {case.case_id}",
        {"article_id": case.article_id, "age": age, "age_unit": age_unit, "gender": gender},
    )


def _mention_from_match(
    text: str,
    tokens: list[Token],
    node: Node,
    token_start: int,
    token_end: int,
    trigger: str,
) -> Mention:
    start = tokens[token_start].start
    end = tokens[token_end - 1].end
    sentence_start, sentence_end = _sentence_span(text, tokens, start)
    return Mention(node, start, end, sentence_start, sentence_end, trigger)


def _add_lexical_entities(
    case: ClinicalCase,
    tokens: list[Token],
    graph: GraphBuilder,
    patient: Node,
) -> list[Mention]:
    text = case.case_text
    mentions: list[Mention] = []

    groups = (
        ("Symptom", SYMPTOMS),
        ("History", HISTORY_TERMS),
        ("Exam", tuple(EXAMS)),
        ("Finding", tuple(FINDINGS)),
        ("Diagnosis", DIAGNOSES),
        ("Medication", MEDICATIONS),
        ("Treatment", tuple(TREATMENTS)),
        ("AnatomicalSite", ANATOMICAL_SITES),
        ("Outcome", tuple(OUTCOMES)),
    )

    direct_relations = {
        "Symptom": "HAS_SYMPTOM",
        "History": "HAS_HISTORY",
        "Exam": "UNDERWENT_EXAM",
        "Finding": "HAS_FINDING",
        "Diagnosis": "DIAGNOSED_WITH",
        "Medication": "TREATED_WITH",
        "Treatment": "TREATED_WITH",
        "Outcome": "HAS_OUTCOME",
    }

    for node_type, terms in groups:
        for term, token_start, token_end in _find_phrases(tokens, terms):
            start = tokens[token_start].start
            sentence_start, sentence_end = _sentence_span(text, tokens, start)
            sentence_folded = text[sentence_start:sentence_end].casefold()

            if node_type == "History" and "history" not in sentence_folded:
                continue
            if node_type == "Diagnosis" and not any(
                trigger in sentence_folded for trigger in DIAGNOSIS_TRIGGERS
            ):
                continue
            if node_type in {"Medication", "Treatment"} and not any(
                trigger in sentence_folded for trigger in TREATMENT_TRIGGERS
            ):
                continue

            polarity = _polarity(tokens, token_start, sentence_start)
            attributes: dict[str, object] = {}
            if node_type == "Symptom":
                attributes = {
                    "polarity": polarity,
                    "duration": _duration(text, start, sentence_start),
                }
            elif node_type == "History":
                attributes = {"subject": "patient", "polarity": polarity, "category": "condition"}
            elif node_type == "Exam":
                attributes = {"modality": EXAMS[term]}
            elif node_type == "Finding":
                attributes = {
                    "source": FINDINGS[term],
                    "polarity": polarity,
                    "certainty": "confirmed",
                }
            elif node_type == "Diagnosis":
                hedged = any(word in sentence_folded for word in ("suggesting", "suspected", "probable"))
                attributes = {
                    "certainty": "excluded" if polarity == "absent" else ("suspected" if hedged else "confirmed"),
                    "polarity": polarity,
                    "role": "differential" if hedged else "principal",
                }
            elif node_type == "Medication":
                attributes = {}
            elif node_type == "Treatment":
                status = "planned" if "planned" in sentence_folded else "performed"
                attributes = {"type": TREATMENTS[term], "status": status}
            elif node_type == "AnatomicalSite":
                words = sentence_folded[max(0, start - sentence_start - 12):start - sentence_start]
                laterality = "right" if "right" in words else ("left" if "left" in words else None)
                attributes = {"laterality": laterality}
            elif node_type == "Outcome":
                attributes = {
                    "type": OUTCOMES[term],
                    "polarity": "absent" if term.startswith(("no ", "without ")) else "present",
                }

            label = term
            node = graph.add_node(node_type, label, attributes)
            mention = _mention_from_match(text, tokens, node, token_start, token_end, term)
            mentions.append(mention)
            relation = direct_relations.get(node_type)
            if relation:
                certainty = "hedged" if node_type == "Diagnosis" and attributes.get("certainty") == "suspected" else "asserted"
                graph.add_edge(patient, node, relation, _edge_attributes(text, mention, certainty=certainty))

    return mentions


def _normalise_number(raw: str) -> Decimal:
    try:
        return Decimal(raw.replace(",", ""))
    except InvalidOperation as error:
        raise ValueError(f"invalid numeric token: {raw!r}") from error


def _normalise_unit(raw: str) -> str:
    folded = raw.casefold().replace("μ", "µ").replace("ul", "µl")
    canonical = {
        "ng/ml": "ng/mL", "ng/dl": "ng/dL", "pg/ml": "pg/mL",
        "mg/dl": "mg/dL", "mg/ml": "mg/mL", "g/dl": "g/dL",
        "iu/ml": "IU/mL", "u/ml": "U/mL", "u/l": "U/L",
        "mmol/l": "mmol/L", "meq/l": "mEq/L", "/µl": "/µL",
        "cells/µl": "cells/µL", "ml": "mL", "iu": "IU", "l": "L",
    }
    return canonical.get(folded, raw)


def _nearest_mention(
    mentions: list[Mention],
    node_types: set[str],
    start: int,
    sentence_start: int,
    sentence_end: int,
) -> Mention | None:
    candidates = [
        mention for mention in mentions
        if mention.node.type in node_types
        and mention.start >= sentence_start
        and mention.end <= sentence_end
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda mention: min(abs(start - mention.start), abs(start - mention.end)))


def _measurement_pairs(tokens: list[Token]):
    """Produz (índice do número, índice da unidade), somente para pares válidos."""
    for index, token in enumerate(tokens[:-1]):
        if token.kind != "NUMBER":
            continue
        unit_index = index + 1
        if tokens[unit_index].kind == "UNIT":
            yield index, unit_index


def _dimension_end(tokens: list[Token], number_index: int, unit_index: int) -> int:
    """Retorna o índice exclusivo de `6cm x 9cm x 2cm`."""
    cursor = unit_index + 1
    while cursor + 2 < len(tokens):
        if tokens[cursor].text.casefold() not in {"x", "×"}:
            break
        if tokens[cursor + 1].kind != "NUMBER" or tokens[cursor + 2].kind != "UNIT":
            break
        if _normalise_unit(tokens[cursor + 2].text) not in {"cm", "mm"}:
            break
        cursor += 3
    return cursor


def _extract_measurements(
    case: ClinicalCase,
    tokens: list[Token],
    graph: GraphBuilder,
    patient: Node,
    mentions: list[Mention],
) -> list[Mention]:
    text = case.case_text
    extracted: list[Mention] = []
    consumed_numbers: set[int] = set()

    for number_index, unit_index in _measurement_pairs(tokens):
        if number_index in consumed_numbers:
            continue
        number = tokens[number_index]
        unit_token = tokens[unit_index]
        unit = _normalise_unit(unit_token.text)
        sentence_start, sentence_end = _sentence_span(text, tokens, number.start)
        sentence = text[sentence_start:sentence_end]

        dimension_end = _dimension_end(tokens, number_index, unit_index)
        is_dimension = unit in {"cm", "mm"}
        if is_dimension:
            raw_size = text[number.start:tokens[dimension_end - 1].end]
            normalized_size = re.sub(r"(?<=\d)(?=[A-Za-zµμ])", " ", raw_size)
            normalized_size = re.sub(r"\s+", " ", normalized_size)
            for index in range(number_index, dimension_end):
                if tokens[index].kind == "NUMBER":
                    consumed_numbers.add(index)
            finding = _nearest_mention(
                mentions, {"Finding"}, number.start, sentence_start, sentence_end
            )
            if finding:
                finding.node.attributes["size"] = normalized_size
            continue

        context_prefix = text[sentence_start:number.start].casefold()
        if re.search(r"(?:normal|reference)\s+range[^.;:]{0,30}$", context_prefix):
            continue

        medication = _nearest_mention(
            mentions, {"Medication"}, number.start, sentence_start, sentence_end
        )
        if medication and unit in {"mg", "g", "mcg", "µg", "IU", "mL"}:
            medication.node.attributes["dose_value"] = _normalise_number(number.text)
            medication.node.attributes["dose_unit"] = unit
            continue

        exam = _nearest_mention(
            mentions, {"Exam"}, number.start, sentence_start, sentence_end
        )
        if exam is None:
            exam_node = graph.add_node("Exam", "laboratory measurement", {"modality": "laboratory"})
            exam = Mention(exam_node, number.start, unit_token.end, sentence_start, sentence_end, "measurement")
            mentions.append(exam)
            graph.add_edge(patient, exam_node, "UNDERWENT_EXAM", _edge_attributes(text, exam))

        range_match = _REFERENCE_RANGE_RE.search(sentence)
        interpretation = None
        interpretation_source = None
        folded_sentence = sentence.casefold()
        for value in ("elevated", "decreased", "abnormal", "positive", "negative", "normal"):
            if re.search(rf"\b{value}\b", folded_sentence):
                if value != "normal" or "normal range" not in folded_sentence:
                    interpretation = value
                    interpretation_source = "stated"
                    break

        attributes: dict[str, object] = {
            "value": _normalise_number(number.text),
            "unit": unit,
            "raw_text": text[number.start:unit_token.end],
            "interpretation": interpretation,
            "interpretation_source": interpretation_source,
        }
        if range_match:
            attributes.update({
                "reference_range_low": Decimal(range_match.group("low")),
                "reference_range_high": Decimal(range_match.group("high")),
                "reference_range_raw": range_match.group(),
            })
            if interpretation is None:
                value = attributes["value"]
                low = attributes["reference_range_low"]
                high = attributes["reference_range_high"]
                interpretation = "decreased" if value < low else ("elevated" if value > high else "normal")
                attributes["interpretation"] = interpretation
                attributes["interpretation_source"] = "derived"

        result_node = graph.add_node(
            "ExamResult",
            f"{_normalise_number(number.text)} {unit}",
            attributes,
            deduplicate=False,
        )
        result_mention = Mention(
            result_node,
            number.start,
            unit_token.end,
            sentence_start,
            sentence_end,
            "value+unit",
        )
        extracted.append(result_mention)
        graph.add_edge(exam.node, result_node, "HAS_RESULT", _edge_attributes(text, result_mention))

    return extracted


def _build_secondary_relations(
    case: ClinicalCase,
    graph: GraphBuilder,
    mentions: list[Mention],
) -> None:
    text = case.case_text
    for finding in (mention for mention in mentions if mention.node.type == "Finding"):
        exam = _nearest_mention(
            mentions, {"Exam"}, finding.start, finding.sentence_start, finding.sentence_end
        )
        if exam:
            graph.add_edge(exam.node, finding.node, "REVEALS", _edge_attributes(text, finding))

    linkable_types = {"Symptom", "Finding", "Treatment"}
    for site in (mention for mention in mentions if mention.node.type == "AnatomicalSite"):
        owner = _nearest_mention(
            mentions, linkable_types, site.start, site.sentence_start, site.sentence_end
        )
        if owner:
            graph.add_edge(owner.node, site.node, "LOCATED_IN", _edge_attributes(text, site))

    evidence_types = {"Symptom", "Finding", "ExamResult", "History"}
    for diagnosis in (mention for mention in mentions if mention.node.type == "Diagnosis"):
        for evidence in mentions:
            if (
                evidence.node.type in evidence_types
                and evidence.node.node_id != diagnosis.node.node_id
                and evidence.sentence_start == diagnosis.sentence_start
            ):
                certainty = "hedged" if diagnosis.node.attributes.get("certainty") == "suspected" else "asserted"
                graph.add_edge(
                    evidence.node,
                    diagnosis.node,
                    "SUPPORTS",
                    _edge_attributes(text, diagnosis, certainty=certainty),
                )


def extract_case(
    case: ClinicalCase,
    tokens: list[Token],
    graph: GraphBuilder,
) -> ExtractionResult:
    """Extrai entidades e relações; todos os offsets continuam no texto original."""
    for token in tokens:
        token.validate_against(case.case_text)
    patient = _extract_patient(case, graph)
    mentions = _add_lexical_entities(case, tokens, graph, patient)
    result_mentions = _extract_measurements(case, tokens, graph, patient, mentions)
    mentions.extend(result_mentions)
    _build_secondary_relations(case, graph, mentions)
    return ExtractionResult(patient, tuple(mentions))
