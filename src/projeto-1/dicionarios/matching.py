from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import nltk
from rapidfuzz import fuzz, process

from normalization import align_normalized_tokens, normalize_term, normalize_token

FUZZY_THRESHOLD = 85.0
MIN_FUZZY_LENGTH = 5


@dataclass(frozen=True)
class Match:
    start: int
    end: int
    matched_key: str
    code: str
    preferred_term: str
    strategy: str
    score: float | None = None


def _break_tie(entries: list[tuple[str, str]], key: str) -> tuple[str, str]:
    if len(entries) == 1:
        return entries[0]

    canonical = [e for e in entries if normalize_term(e[1]) == key]
    if len(canonical) == 1:
        return canonical[0]

    return sorted(entries, key=lambda e: e[0])[0]


def greedy_match(
    raw_tokens: list[str],
    gazetteer: dict[str, list[tuple[str, str]]],
    max_window: int = 4,
    normalize_fn: Callable[[str], str] = normalize_token,
) -> tuple[list[Match], list[int]]:
    aligned = align_normalized_tokens(raw_tokens, normalize_fn)
    matches: list[Match] = []
    unmatched: list[int] = []

    i, n = 0, len(aligned)
    while i < n:
        found = False
        for w in range(min(max_window, n - i), 0, -1):
            key = " ".join(tok for _, tok in aligned[i : i + w])
            if key in gazetteer:
                start = aligned[i][0]
                end = aligned[i + w - 1][0] + 1
                code, preferred_term = _break_tie(gazetteer[key], key)
                strategy = "exact" if w == 1 else "longest"
                matches.append(
                    Match(start, end, key, code, preferred_term, strategy)
                )
                i += w
                found = True
                break
        if not found:
            unmatched.append(aligned[i][0])
            i += 1

    return matches, unmatched


def fuzzy_match_leftover(
    raw_tokens: list[str],
    unmatched_indices: list[int],
    gazetteer: dict[str, list[tuple[str, str]]],
    threshold: float = FUZZY_THRESHOLD,
) -> list[Match]:
    if not gazetteer:
        return []

    keys = list(gazetteer.keys())
    matches: list[Match] = []

    for index in unmatched_indices:
        token = normalize_token(raw_tokens[index])
        if not token or len(token) < MIN_FUZZY_LENGTH:
            continue

        result = process.extractOne(
            token, keys, scorer=fuzz.ratio, score_cutoff=threshold
        )
        if result is None:
            continue

        matched_key, score, _ = result
        code, preferred_term = _break_tie(gazetteer[matched_key], matched_key)
        matches.append(
            Match(
                index,
                index + 1,
                matched_key,
                code,
                preferred_term,
                "fuzzy",
                score=score,
            )
        )

    return matches


def match_text(
    raw_tokens: list[str],
    gazetteer: dict[str, list[tuple[str, str]]],
    max_window: int = 4,
    fuzzy_threshold: float = FUZZY_THRESHOLD,
) -> list[Match]:
    matches, unmatched = greedy_match(raw_tokens, gazetteer, max_window)
    matches += fuzzy_match_leftover(raw_tokens, unmatched, gazetteer, fuzzy_threshold)
    return sorted(matches, key=lambda m: m.start)


def link_label_to_concept(
    label: str,
    gazetteer: dict[str, list[tuple[str, str]]],
    max_window: int = 4,
    fuzzy_threshold: float = FUZZY_THRESHOLD,
    tokenize_fn: Callable[[str], list[str]] = nltk.word_tokenize,
) -> Match | None:
    tokens = tokenize_fn(label)
    if not tokens:
        return None

    matches, _ = greedy_match(tokens, gazetteer, max_window)
    if matches:
        return max(matches, key=lambda m: m.end - m.start)

    if not gazetteer:
        return None

    whole_label = normalize_term(label)
    if not whole_label or len(whole_label) < MIN_FUZZY_LENGTH:
        return None

    result = process.extractOne(
        whole_label, list(gazetteer.keys()), scorer=fuzz.ratio, score_cutoff=fuzzy_threshold
    )
    if result is None:
        return None

    matched_key, score, _ = result
    code, preferred_term = _break_tie(gazetteer[matched_key], matched_key)
    return Match(0, len(tokens), matched_key, code, preferred_term, "fuzzy", score=score)
