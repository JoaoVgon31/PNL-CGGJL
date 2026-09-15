"""As 4 condições do experimento de remoção de stop-words."""

from enum import Enum, auto


class Condition(Enum):
    """BASELINE = referência. As outras 3 variam onde/se a proteção é aplicada."""

    BASELINE = auto()
    NAIVE_UNPROTECTED = auto()
    GUARDED_GLOBAL = auto()
    GUARDED_LABEL = auto()


WORDLISTS = ("nltk_stopwords", "spacy_stopwords", "custom_clinical")
