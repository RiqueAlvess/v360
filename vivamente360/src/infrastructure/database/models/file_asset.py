import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database.models.base import Base


class FileAsset(Base):
    """Metadados de arquivos armazenados no Cloudflare R2.

    O binário nunca é armazenado no servidor FastAPI — apenas os metadados
    ficam no banco. O arquivo em si reside no bucket R2 identificado por r2_key.
from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.models.base import Base

if TYPE_CHECKING:
    from src.infrastructure.database.models.company import Company
    from src.infrastructure.database.models.user import User


# Contextos válidos para file_assets — ampliar conforme novos módulos
CONTEXTO_CHECKLIST_EVIDENCIA: str = "checklist_evidencia"


class FileAsset(Base):
    """Ativo de arquivo compartilhado entre módulos do sistema.

    Armazena APENAS os metadados dos arquivos físicos. O conteúdo binário
    reside no Cloudflare R2 e NUNCA é servido diretamente pelo FastAPI —
    apenas via signed URLs geradas sob demanda (Regra do projeto).

    Soft delete: o campo `deletado` marca exclusão lógica. O arquivo físico
    no R2 é removido de forma assíncrona por um worker de limpeza.

    Contextos suportados:
        - 'checklist_evidencia': evidência de conclusão de item NR-1
        - (outros contextos adicionados por módulos futuros)
    """

    __tablename__ = "file_assets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    r2_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    contexto: Mapped[str] = mapped_column(String(50), nullable=False)
    referencia_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    deletado: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
        sa.ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contexto: Mapped[str] = mapped_column(sa.String(100), nullable=False)
    referencia_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    nome_original: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    tamanho_bytes: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    content_type: Mapped[str] = mapped_column(sa.String(200), nullable=False)
    storage_key: Mapped[str] = mapped_column(sa.String(500), nullable=False)
    deletado: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=False,
        server_default=sa.text("false"),
    )
    deletado_em: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=True,
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )

    # Relationships
    company: Mapped["Company"] = relationship("Company")
    criado_por_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[created_by],
    )
