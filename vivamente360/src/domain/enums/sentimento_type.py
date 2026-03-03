from enum import Enum


class SentimentoType(str, Enum):
    """Classificação de sentimento para textos livres do survey HSE-IT.

    Escala crescente de negatividade:
    - POSITIVO: Conteúdo otimista, satisfação, engajamento.
    - NEUTRO: Conteúdo informativo ou ambíguo sem carga emocional clara.
    - NEGATIVO: Insatisfação, frustração ou preocupação moderada.
    - CRITICO: Sofrimento intenso, risco psicossocial elevado.
    """

    POSITIVO = "positivo"
    NEUTRO = "neutro"
    NEGATIVO = "negativo"
    CRITICO = "critico"
