import uuid
from datetime import date

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.models.base import Base


class DimTempo(Base):
    """Dimensão de tempo do modelo estrela.

    Decompõe a data em componentes analíticos para filtros eficientes por
    período, trimestre, mês, etc. Uma linha por data distinta.
    """

    __tablename__ = "dim_tempo"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    data: Mapped[date] = mapped_column(sa.Date, nullable=False, unique=True, index=True)
    ano: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    mes: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    dia: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    trimestre: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    dia_semana: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
    semana_ano: Mapped[int] = mapped_column(sa.SmallInteger, nullable=False)
