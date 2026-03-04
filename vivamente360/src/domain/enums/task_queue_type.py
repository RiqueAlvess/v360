from enum import Enum


class TaskQueueType(str, Enum):
    """Tipos de tarefas processadas pela fila assíncrona."""

    COMPUTE_SCORES = "compute_scores"
    SEND_EMAIL = "send_email"
    SEND_INVITATIONS = "send_invitations"
    GENERATE_REPORT = "generate_report"
    CLEANUP_EXPIRED_TOKENS = "cleanup_expired_tokens"
    NOTIFY_PLAN_COMPLETED = "notify_plan_completed"
    ANALYZE_SENTIMENT = "analyze_sentiment"
    RUN_AI_ANALYSIS = "run_ai_analysis"
    # Módulo 07: notifica admins ao receber novo relato no canal de denúncias
    NOTIFY_WHISTLEBLOWER_ADMIN = "notify_whistleblower_admin"
    # Módulo 08: job diário de alertas de campanhas e planos de ação
    CHECK_CAMPAIGN_ALERTS = "check_campaign_alerts"
