# Importar todos os modelos para garantir que estejam registrados no metadata do Base.
# OBRIGATÓRIO: o env.py do Alembic importa este módulo para autogenerate funcionar.
from src.infrastructure.database.models.base import Base, TimestampMixin
from src.infrastructure.database.models.campaign import Campaign
from src.infrastructure.database.models.file_asset import FileAsset
from src.infrastructure.database.models.checklist_item import ChecklistItem
from src.infrastructure.database.models.checklist_template import ChecklistTemplate
from src.infrastructure.database.models.company import Company
from src.infrastructure.database.models.dim_estrutura import DimEstrutura
from src.infrastructure.database.models.dim_tempo import DimTempo
from src.infrastructure.database.models.email_log import EmailLog
from src.infrastructure.database.models.fact_score_dimensao import FactScoreDimensao
from src.infrastructure.database.models.file_asset import FileAsset
from src.infrastructure.database.models.invitation import Invitation
from src.infrastructure.database.models.job_position import JobPosition
from src.infrastructure.database.models.organizational_unit import OrganizationalUnit
from src.infrastructure.database.models.refresh_token import RefreshToken
from src.infrastructure.database.models.sector import Sector
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
    "OrganizationalUnit",
    "Sector",
    "JobPosition",
    "DimTempo",
    "DimEstrutura",
    "FactScoreDimensao",
    "ChecklistTemplate",
    "ChecklistItem",
    "FileAsset",
]
