"""Carrega as listas de stop-words de lexicon/data/*.txt."""

from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent / "data"


def load_list(name: str) -> frozenset[str]:
    """Carrega uma lista por nome (sem extensão), uma palavra por linha."""
    path = _DATA_DIR / f"{name}.txt"
    words = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            word = line.strip().lower()
            if word:
                words.add(word)
    return frozenset(words)
