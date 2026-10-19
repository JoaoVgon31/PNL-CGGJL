"""Texto, tokens, frases e casos de avaliação compartilhados pelas etapas."""
from .corpus import CASOS_PADRAO, GOLD_PADRAO, REPO, casos_gold, iter_casos, iter_registros, ler_casos
from .texto import dividir_frases, etiquetar, tokenizar

__all__ = ["REPO", "CASOS_PADRAO", "GOLD_PADRAO", "casos_gold", "iter_casos",
           "iter_registros", "ler_casos", "tokenizar", "dividir_frases", "etiquetar"]
