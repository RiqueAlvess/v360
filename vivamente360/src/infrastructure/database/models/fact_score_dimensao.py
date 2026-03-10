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
    from src.infrastructure.database.models.organizational_unit import OrganizationalUnit
    from src.infrastructure.database.models.sector import Sector
    from src.infrastructure.database.models.job_position import JobPosition


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

    unidade_id / setor_id / cargo_id: desnormalização intencional de dim_estrutura
    para filtragem eficiente sem JOIN no hot path do dashboard (Módulo 09).
    NULL para registros de nível empresa (sem hierarquia organizacional).
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
        sa.Enum(DimensaoHSE, name="dimensao_hse", create_type=False, values_callable=lambda obj: [e.value for e in obj]),
        nullable=False,
    )
    score_medio: Mapped[Decimal] = mapped_column(sa.Numeric(5, 2), nullable=False)
    nivel_risco: Mapped[NivelRisco] = mapped_column(
        sa.Enum(NivelRisco, name="nivel_risco", create_type=False, values_callable=lambda obj: [e.value for e in obj]),
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
    # Módulo 09: colunas desnormalizadas de dim_estrutura para filtros eficientes
    unidade_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("organizational_units.id", ondelete="SET NULL"),
        nullable=True,
    )
    setor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("sectors.id", ondelete="SET NULL"),
        nullable=True,
    )
    cargo_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("job_positions.id", ondelete="SET NULL"),
        nullable=True,
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
    unidade: Mapped[Optional["OrganizationalUnit"]] = relationship(
        "OrganizationalUnit", foreign_keys=[unidade_id]
    )
    setor: Mapped[Optional["Sector"]] = relationship(
        "Sector", foreign_keys=[setor_id]
    )
    cargo: Mapped[Optional["JobPosition"]] = relationship(
        "JobPosition", foreign_keys=[cargo_id]
    )
