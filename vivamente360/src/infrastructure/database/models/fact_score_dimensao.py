import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.enums.dimensao_hse import DimensaoHSE
from src.domain.enums.nivel_risco import NivelRisco
from src.infrastructure.database.models.base import Base

if TYPE_CHECKING:
    from src.infrastructure.database.models.campaign import Campaign
    from src.infrastructure.database.models.dim_estrutura import DimEstrutura
    from src.infrastructure.database.models.dim_tempo import DimTempo


class FactScoreDimensao(Base):
    """Tabela fato do modelo estrela — scores pré-computados por dimensão HSE-IT.

    Populada exclusivamente por workers assíncronos após cada submissão de
    survey_response. O dashboard lê APENAS desta tabela — zero cálculos
    no request/response cycle (Regra R3).

    A constraint UNIQUE em (campaign_id, dim_tempo_id, dim_estrutura_id, dimensao)
    garante idempotência: o worker pode executar múltiplas vezes sem duplicar dados.

    sentimento_score_medio: média dos scores de sentimento das respostas que
    forneceram texto livre com consentimento. NULL quando nenhuma resposta da
    campanha contém análise de sentimento concluída.
    """

    __tablename__ = "fact_score_dimensao"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dim_tempo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("dim_tempo.id", ondelete="RESTRICT"),
        nullable=False,
    )
    dim_estrutura_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("dim_estrutura.id", ondelete="RESTRICT"),
        nullable=False,
    )
    dimensao: Mapped[DimensaoHSE] = mapped_column(
        sa.Enum(DimensaoHSE, name="dimensao_hse"),
        nullable=False,
    )
    score_medio: Mapped[Decimal] = mapped_column(sa.Numeric(5, 2), nullable=False)
    nivel_risco: Mapped[NivelRisco] = mapped_column(
        sa.Enum(NivelRisco, name="nivel_risco"),
        nullable=False,
    )
    total_respostas: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    # Score médio de sentimento agregado (NULL se nenhuma resposta tem sentimento)
    sentimento_score_medio: Mapped[Optional[Decimal]] = mapped_column(
        sa.Numeric(4, 3),
        nullable=True,
    )
    computed_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "campaign_id",
            "dim_tempo_id",
            "dim_estrutura_id",
            "dimensao",
            name="uq_fact_score_dimensao",
        ),
    )

    # Relationships
    campaign: Mapped["Campaign"] = relationship("Campaign")
    dim_tempo: Mapped["DimTempo"] = relationship("DimTempo")
    dim_estrutura: Mapped["DimEstrutura"] = relationship("DimEstrutura")
