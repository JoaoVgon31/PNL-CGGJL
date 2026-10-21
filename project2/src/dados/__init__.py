"""Geração do silver standard e da linha de base das regras do Projeto 1 (#29)."""
from .silver import (
    COLUNAS_MENCOES,
    COLUNAS_RELACOES,
    DADOS,
    REGRAS,
    REGRAS_RELACOES,
    SILVER,
    SILVER_BIO,
    SILVER_RELACOES,
    gerar,
    ler_silver,
    mencoes_das_regras,
)

__all__ = [
    "COLUNAS_MENCOES",
    "COLUNAS_RELACOES",
    "DADOS",
    "REGRAS",
    "REGRAS_RELACOES",
    "SILVER",
    "SILVER_BIO",
    "SILVER_RELACOES",
    "gerar",
    "ler_silver",
    "mencoes_das_regras",
]
