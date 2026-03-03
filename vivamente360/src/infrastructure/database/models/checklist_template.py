import uuid
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.models.base import Base


class ChecklistTemplate(Base):
    """Template canônico de item NR-1 — definição imutável dos requisitos de conformidade.

    Populada via seed (seeds/checklist_nr1.py) com os 15+ itens canônicos
    da NR-1 revisada (Portaria MTE 1.419/2024). Não possui timestamps pois
    é gerenciada por migrações e seeds, não pelo ciclo de vida da aplicação.
    """

    __tablename__ = "checklist_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    codigo: Mapped[str] = mapped_column(
        sa.String(20),
        nullable=False,
        unique=True,
        index=True,
    )
    descricao: Mapped[str] = mapped_column(sa.Text, nullable=False)
    categoria: Mapped[str] = mapped_column(
        sa.String(100),
        nullable=False,
        index=True,
    )
    obrigatorio: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
        server_default=sa.text("true"),
    )
    prazo_dias: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)
    ordem: Mapped[int] = mapped_column(
        sa.SmallInteger,
        nullable=False,
        default=0,
        server_default=sa.text("0"),
    )
