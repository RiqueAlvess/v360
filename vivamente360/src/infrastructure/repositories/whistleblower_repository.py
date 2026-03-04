"""Repositório do Canal de Denúncias Anônimo — Módulo 07.

Regra R2: Repositories só persistem — nenhuma regra de negócio aqui.
Regra R1: Type hints completos em todos os métodos e retornos.
Regra R4: list_by_company() retorna tupla (items, total) para paginação.

ANONIMATO: este repositório nunca armazena o token raw.
Recebe apenas o token_hash (SHA-256) e retorna o relato sem dados identificáveis.
"""
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums.user_role import UserRole
from src.domain.enums.whistleblower_status import WhistleblowerStatus
from src.infrastructure.database.models.company import Company
from src.infrastructure.database.models.user import User
from src.infrastructure.database.models.whistleblower_report import WhistleblowerReport

# Limite máximo de itens por página — Regra R4
_PAGE_SIZE_MAX: int = 100


class WhistleblowerRepository(ABC):
    """Interface abstrata do repositório de relatos do canal de denúncias."""

    @abstractmethod
    async def get_company_id_by_slug(self, slug: str) -> Optional[UUID]:
        """Busca o company_id pelo slug público da empresa.

        Usado em endpoints públicos (sem JWT) para resolver o slug da URL
        ao company_id necessário para definir o contexto RLS.
        """
        ...

    @abstractmethod
    async def create(
        self,
        company_id: UUID,
        token_hash: str,
        categoria: str,
        descricao: str,
        anonimo: bool,
        nome_opcional: Optional[str],
    ) -> WhistleblowerReport:
        """Cria e persiste um novo relato de denúncia.

        Args:
            company_id: UUID da empresa proprietária do canal.
            token_hash: SHA-256 hex do token entregue ao denunciante.
                        O token raw NUNCA é armazenado neste método.
            categoria: Categoria da denúncia (WhistleblowerCategoria value).
            descricao: Conteúdo do relato em texto livre.
            anonimo: True se o denunciante optou pelo anonimato (padrão).
            nome_opcional: Nome do denunciante, somente se anonimo=False.

        Returns:
            O WhistleblowerReport recém-criado com id gerado.
        """
        ...

    @abstractmethod
    async def get_by_token_hash(
        self, token_hash: str
    ) -> Optional[WhistleblowerReport]:
        """Busca relato pelo SHA-256 do token de acompanhamento.

        RLS filtra automaticamente por company_id — o context deve estar
        configurado antes desta chamada (SET LOCAL app.company_id = ...).

        Args:
            token_hash: SHA-256 hex digest do token do denunciante.

        Returns:
            O WhistleblowerReport se encontrado, None caso contrário.
        """
        ...

    @abstractmethod
    async def list_by_company(
        self,
        company_id: UUID,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
    ) -> tuple[list[WhistleblowerReport], int]:
        """Lista relatos da empresa com paginação e filtro opcional por status.

        Args:
            company_id: UUID da empresa autenticada.
            page: Número da página (1-indexed).
            page_size: Itens por página (máximo 100).
            status: Filtro opcional por status do relato.

        Returns:
            Tupla (items, total) com os relatos paginados e o total geral.
        """
        ...

    @abstractmethod
    async def update_resposta(
        self,
        report_id: UUID,
        resposta_institucional: str,
        status: WhistleblowerStatus,
        respondido_por: UUID,
    ) -> Optional[WhistleblowerReport]:
        """Registra a resposta institucional ao relato e atualiza o status.

        Args:
            report_id: UUID do relato a responder.
            resposta_institucional: Texto da resposta oficial da empresa.
            status: Novo status após resposta (em_analise, concluido, arquivado).
            respondido_por: UUID do usuário admin/compliance que respondeu.

        Returns:
            O WhistleblowerReport atualizado, ou None se não encontrado.
        """
        ...

    @abstractmethod
    async def get_by_id(self, report_id: UUID) -> Optional[WhistleblowerReport]:
        """Busca relato pelo UUID primário.

        RLS filtra automaticamente por company_id — o contexto deve estar
        configurado antes desta chamada.

        Args:
            report_id: UUID do relato.

        Returns:
            O WhistleblowerReport se encontrado, None caso contrário.
        """
        ...

    @abstractmethod
    async def get_admin_encrypted_emails_by_company(
        self, company_id: UUID
    ) -> list[bytes]:
        """Retorna os emails cifrados (AES-256-GCM) dos admins ativos da empresa.

        Usado para enviar notificações a admins ao receber novo relato.
        Os bytes são o email cifrado via encrypt_data(), armazenado como LargeBinary.

        Args:
            company_id: UUID da empresa.

        Returns:
            Lista de bytes contendo os emails cifrados dos admins ativos.
        """
        ...


class SQLWhistleblowerRepository(WhistleblowerRepository):
    """Implementação SQLAlchemy 2.x do repositório de relatos de denúncias."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_company_id_by_slug(self, slug: str) -> Optional[UUID]:
        """Busca company_id pelo slug.

        O slug é um campo público e imutável — não contém dados sensíveis.
        A consulta é feita sem filtro de RLS por company_id (chicken-and-egg:
        precisamos do company_id para ativar o contexto RLS). Isso é seguro
        porque retornamos apenas o UUID, sem expor outros dados da empresa.

        A policy `tenant_isolation_companies` aplica-se apenas ao role `app_user`.
        O role de conexão da aplicação (owner/superuser) não é afetado.
        """
        result = await self._session.execute(
            select(Company.id).where(
                Company.slug == slug,
                Company.ativo.is_(True),
            )
        )
        row = result.scalar_one_or_none()
        return row  # type: ignore[return-value]

    async def create(
        self,
        company_id: UUID,
        token_hash: str,
        categoria: str,
        descricao: str,
        anonimo: bool,
        nome_opcional: Optional[str],
    ) -> WhistleblowerReport:
        """Cria e persiste o relato. O token_hash é o único vínculo com o denunciante."""
        report = WhistleblowerReport(
            id=uuid.uuid4(),
            company_id=company_id,
            token_hash=token_hash,
            categoria=categoria,
            descricao=descricao,
            anonimo=anonimo,
            nome_opcional=nome_opcional,
        )
        self._session.add(report)
        await self._session.flush()
        return report

    async def get_by_token_hash(
        self, token_hash: str
    ) -> Optional[WhistleblowerReport]:
        """Busca relato pelo token_hash. RLS garante isolamento por empresa."""
        result = await self._session.execute(
            select(WhistleblowerReport).where(
                WhistleblowerReport.token_hash == token_hash
            )
        )
        return result.scalar_one_or_none()

    async def list_by_company(
        self,
        company_id: UUID,
        page: int = 1,
        page_size: int = 20,
        status: Optional[str] = None,
    ) -> tuple[list[WhistleblowerReport], int]:
        """Lista relatos da empresa com paginação, do mais recente ao mais antigo."""
        page_size = min(page_size, _PAGE_SIZE_MAX)
        offset = (page - 1) * page_size

        base_stmt = select(WhistleblowerReport).where(
            WhistleblowerReport.company_id == company_id
        )
        if status is not None:
            base_stmt = base_stmt.where(WhistleblowerReport.status == status)

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_result = await self._session.execute(count_stmt)
        total: int = total_result.scalar_one()

        items_stmt = (
            base_stmt.order_by(WhistleblowerReport.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items_result = await self._session.execute(items_stmt)
        reports: list[WhistleblowerReport] = list(items_result.scalars().all())

        return reports, total

    async def update_resposta(
        self,
        report_id: UUID,
        resposta_institucional: str,
        status: WhistleblowerStatus,
        respondido_por: UUID,
    ) -> Optional[WhistleblowerReport]:
        """Registra resposta institucional e atualiza status e timestamp."""
        result = await self._session.execute(
            select(WhistleblowerReport).where(WhistleblowerReport.id == report_id)
        )
        report = result.scalar_one_or_none()
        if report is None:
            return None

        report.resposta_institucional = resposta_institucional
        report.status = status
        report.respondido_por = respondido_por
        report.respondido_em = datetime.now(tz=timezone.utc)
        await self._session.flush()
        return report

    async def get_by_id(self, report_id: UUID) -> Optional[WhistleblowerReport]:
        """Busca relato pelo UUID. RLS garante isolamento por empresa."""
        result = await self._session.execute(
            select(WhistleblowerReport).where(WhistleblowerReport.id == report_id)
        )
        return result.scalar_one_or_none()

    async def get_admin_encrypted_emails_by_company(
        self, company_id: UUID
    ) -> list[bytes]:
        """Busca emails cifrados dos admins ativos da empresa para notificação."""
        result = await self._session.execute(
            select(User.email_criptografado).where(
                User.company_id == company_id,
                User.role == UserRole.ADMIN,
                User.ativo.is_(True),
            )
        )
        return list(result.scalars().all())
