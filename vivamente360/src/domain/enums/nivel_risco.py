from enum import Enum


class NivelRisco(str, Enum):
    """Níveis de risco psicossocial para classificação de scores HSE-IT.

    Ordem crescente de severidade: aceitavel < moderado < importante < critico.
    """

    ACEITAVEL = "aceitavel"
    MODERADO = "moderado"
    IMPORTANTE = "importante"
    CRITICO = "critico"
