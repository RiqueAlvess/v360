# Importar todos os modelos para garantir que estejam registrados no metadata do Base.
# OBRIGATÓRIO: o env.py do Alembic importa este módulo para autogenerate funcionar.
from src.infrastructure.database.models.base import Base, TimestampMixin
from src.infrastructure.database.models.campaign import Campaign
from src.infrastructure.database.models.company import Company
from src.infrastructure.database.models.email_log import EmailLog
from src.infrastructure.database.models.invitation import Invitation
from src.infrastructure.database.models.refresh_token import RefreshToken
from src.infrastructure.database.models.survey_response import SurveyResponse
from src.infrastructure.database.models.task_queue import TaskQueue
from src.infrastructure.database.models.user import User

__all__ = [
    "Base",
    "TimestampMixin",
    "Company",
    "User",
    "RefreshToken",
    "Campaign",
    "Invitation",
    "SurveyResponse",
    "TaskQueue",
    "EmailLog",
]
