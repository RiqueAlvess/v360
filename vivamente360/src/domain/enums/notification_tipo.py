from enum import Enum


class NotificationTipo(str, Enum):
    """Tipos de eventos que geram notificações in-app."""

    CAMPANHA_ENCERRADA = "campanha_encerrada"
    RELATORIO_PRONTO = "relatorio_pronto"
    NOVA_DENUNCIA = "nova_denuncia"
    PLANO_VENCENDO = "plano_vencendo"
    ANALISE_IA_CONCLUIDA = "analise_ia_concluida"
    CHECKLIST_CONCLUIDO = "checklist_concluido"
    TAXA_RESPOSTA_BAIXA = "taxa_resposta_baixa"
