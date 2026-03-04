from enum import Enum


class WhistleblowerCategoria(str, Enum):
    """Categorias de denúncia disponíveis no canal anônimo (Módulo 07 — NR-1)."""

    ASSEDIO_MORAL = "assedio_moral"
    ASSEDIO_SEXUAL = "assedio_sexual"
    DISCRIMINACAO = "discriminacao"
    VIOLENCIA = "violencia"
    CORRUPCAO = "corrupcao"
    OUTRO = "outro"
