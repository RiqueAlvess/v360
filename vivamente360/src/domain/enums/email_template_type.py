from enum import Enum


class EmailTemplateType(str, Enum):
    """Templates de email disponíveis no sistema."""

    INVITATION_EMAIL = "invitation_email"
    REMINDER_EMAIL = "reminder_email"
    RESULTS_READY_EMAIL = "results_ready_email"
    CAMPAIGN_CLOSED_EMAIL = "campaign_closed_email"
