from enum import Enum


class CampaignStatus(str, Enum):
    """Estados possíveis de uma campanha psicossocial."""

    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
