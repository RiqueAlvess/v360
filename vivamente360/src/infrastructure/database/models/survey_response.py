import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.enums.sentimento_type import SentimentoType
from src.infrastructure.database.models.base import Base

if TYPE_CHECKING:
    from src.infrastructure.database.models.campaign import Campaign


class SurveyResponse(Base):
    """Resposta anônima de pesquisa — sem FK para invitation (Blind Drop)."""

    __tablename__ = "survey_responses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # FK para campanha apenas — sem vínculo com invitation para garantir anonimato
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Respostas estruturadas em JSONB para flexibilidade de schema de questionário
    respostas: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    anonimizado: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    # Campo livre — LGPD: armazenado criptografado (AES-256-GCM via CryptoService)
    # Nullable: preenchimento é opcional e requer consentimento_texto_livre=True
    texto_livre: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    # Classificação qualitativa de sentimento — populada pelo AnalyzeSentimentHandler
    sentimento: Mapped[Optional[SentimentoType]] = mapped_column(
        sa.Enum(SentimentoType, name="sentimento_type", create_type=False, values_callable=lambda obj: [e.value for e in obj]),
        nullable=True,
    )
    # Score numérico de sentimento: -1.0 (crítico) a +1.0 (positivo)
    # Populado pelo AnalyzeSentimentHandler via OpenRouter
    sentimento_score: Mapped[Optional[Decimal]] = mapped_column(
        sa.Numeric(4, 3),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    # Relationship
    campaign: Mapped["Campaign"] = relationship(
        "Campaign", back_populates="survey_responses"
    )
