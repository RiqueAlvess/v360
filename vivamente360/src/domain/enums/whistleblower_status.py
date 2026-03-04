from enum import Enum


class WhistleblowerStatus(str, Enum):
    """Status de processamento de um relato do canal de denúncias anônimo."""

    RECEBIDO = "recebido"
    EM_ANALISE = "em_analise"
    CONCLUIDO = "concluido"
    ARQUIVADO = "arquivado"
