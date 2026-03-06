"""Repositório de campanhas de avaliação psicossocial.

Regra R2: Repositories só persistem — nenhuma regra de negócio aqui.
Regra R1: Type hints completos em todos os métodos.
Regra R4: list_by_company() e list_with_filters() retornam tupla (items, total).
Regra R5: RLS ativo via SET LOCAL app.company_id na sessão — não duplicar filtros manuais.
"""
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums.campaign_status import CampaignStatus
from src.infrastructure.database.models.campaign import Campaign
from src.infrastructure.database.models.invitation import Invitation
from src.infrastructure.database.models.survey_response import SurveyResponse

# Limite máximo de itens por página — Regra R4
_PAGE_SIZE_MAX: int = 100


@dataclass
class CampaignStats:
    """Dados agregados de uma campanha com contagens de convites e respostas."""

    campaign: Campaign
    total_convites: int
    total_respostas: int


class CampaignRepository(ABC):
    """Interface abstrata do repositório de campanhas."""

    @abstractmethod
    async def get_by_id(self, campaign_id: UUID) -> Optional[Campaign]:
        """Busca uma campanha pelo seu UUID."""
        ...

    @abstractmethod
    async def list_by_company(
        self,
        company_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Campaign], int]:
        """Lista campanhas de uma empresa com paginação.

        Returns:
            Tupla (items, total) com as campanhas paginadas e o total geral.
        """
        ...

    @abstractmethod
    async def list_with_filters(
        self,
        company_id: UUID,
        status: Optional[CampaignStatus] = None,
        data_inicio_gte: Optional[date] = None,
        data_fim_lte: Optional[date] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Campaign], int]:
        """Lista campanhas da empresa com filtros opcionais e paginação.

        Args:
            company_id: UUID da empresa proprietária (R5: respeitado pelo RLS).
            status: Filtrar pelo status da campanha, se fornecido.
            data_inicio_gte: Campanhas iniciadas em ou após esta data.
            data_fim_lte: Campanhas encerradas em ou antes desta data.
            page: Número da página (1-indexed).
            page_size: Itens por página (máximo 100).

        Returns:
            Tupla (items, total) com as campanhas filtradas e o total geral.
        """
        ...

    @abstractmethod
    async def create(
        self,
        company_id: UUID,
        nome: str,
        data_inicio: date,
        data_fim: date,
    ) -> Campaign:
        """Cria e persiste uma nova campanha.

        Args:
            company_id: UUID da empresa proprietária.
            nome: Nome descritivo da campanha.
            data_inicio: Data de início do período de avaliação.
            data_fim: Data de encerramento do período de avaliação.

        Returns:
            A campanha recém-criada com id gerado.
        """
        ...

    @abstractmethod
    async def update(
        self,
        campaign_id: UUID,
        nome: Optional[str] = None,
        data_inicio: Optional[date] = None,
        data_fim: Optional[date] = None,
        status: Optional[CampaignStatus] = None,
    ) -> Campaign:
        """Atualiza campos da campanha parcialmente.

        Apenas os campos fornecidos (não-None) são atualizados.

        Args:
            campaign_id: UUID da campanha a atualizar.
            nome: Novo nome, se deve ser alterado.
            data_inicio: Nova data de início, se deve ser alterada.
            data_fim: Nova data de encerramento, se deve ser alterada.
            status: Novo status, se deve ser alterado.

        Returns:
            A Campaign com os campos atualizados.
        """
        ...

    @abstractmethod
    async def update_status(
        self,
        campaign_id: UUID,
        status: CampaignStatus,
    ) -> Campaign:
        """Atualiza o status de uma campanha.

        Returns:
            A Campaign com o status atualizado.
        """
        ...

    @abstractmethod
    async def get_campaign_with_stats(
        self,
        campaign_id: UUID,
    ) -> Optional[CampaignStats]:
        """Busca uma campanha com contagens agregadas de convites e respostas.

        Args:
            campaign_id: UUID da campanha.

        Returns:
            CampaignStats com a campanha e contagens, ou None se não encontrada.
        """
        ...


class SQLCampaignRepository(CampaignRepository):
    """Implementação SQLAlchemy 2.x do repositório de campanhas."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, campaign_id: UUID) -> Optional[Campaign]:
        """Busca campanha pelo UUID, retorna None se não encontrada."""
        result = await self._session.execute(
            select(Campaign).where(Campaign.id == campaign_id)
        )
        return result.scalar_one_or_none()

    async def list_by_company(
        self,
        company_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Campaign], int]:
        """Lista campanhas da empresa com paginação, ordenadas por data de criação desc."""
        page_size = min(page_size, _PAGE_SIZE_MAX)
        offset = (page - 1) * page_size

        base_stmt = select(Campaign).where(Campaign.company_id == company_id)

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_result = await self._session.execute(count_stmt)
        total: int = total_result.scalar_one()

        items_stmt = (
            base_stmt
            .order_by(Campaign.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items_result = await self._session.execute(items_stmt)
        campaigns: list[Campaign] = list(items_result.scalars().all())

        return campaigns, total

    async def list_with_filters(
        self,
        company_id: UUID,
        status: Optional[CampaignStatus] = None,
        data_inicio_gte: Optional[date] = None,
        data_fim_lte: Optional[date] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Campaign], int]:
        """Lista campanhas com filtros opcionais e paginação (R4)."""
        page_size = min(page_size, _PAGE_SIZE_MAX)
        offset = (page - 1) * page_size

        base_stmt = select(Campaign).where(Campaign.company_id == company_id)

        if status is not None:
            base_stmt = base_stmt.where(Campaign.status == status)
        if data_inicio_gte is not None:
            base_stmt = base_stmt.where(Campaign.data_inicio >= data_inicio_gte)
        if data_fim_lte is not None:
            base_stmt = base_stmt.where(Campaign.data_fim <= data_fim_lte)

        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_result = await self._session.execute(count_stmt)
        total: int = total_result.scalar_one()

        items_stmt = (
            base_stmt
            .order_by(Campaign.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items_result = await self._session.execute(items_stmt)
        campaigns: list[Campaign] = list(items_result.scalars().all())

        return campaigns, total

    async def create(
        self,
        company_id: UUID,
        nome: str,
        data_inicio: date,
        data_fim: date,
    ) -> Campaign:
        """Cria e persiste a campanha, retornando o objeto com id gerado."""
        campaign = Campaign(
            id=uuid.uuid4(),
            company_id=company_id,
            nome=nome,
            data_inicio=data_inicio,
            data_fim=data_fim,
        )
        self._session.add(campaign)
        await self._session.flush()
        return campaign

    async def update(
        self,
        campaign_id: UUID,
        nome: Optional[str] = None,
        data_inicio: Optional[date] = None,
        data_fim: Optional[date] = None,
        status: Optional[CampaignStatus] = None,
    ) -> Campaign:
        """Atualiza apenas os campos fornecidos da campanha."""
        updates: dict = {}
        if nome is not None:
            updates["nome"] = nome
        if data_inicio is not None:
            updates["data_inicio"] = data_inicio
        if data_fim is not None:
            updates["data_fim"] = data_fim
        if status is not None:
            updates["status"] = status

        stmt = (
            update(Campaign)
            .where(Campaign.id == campaign_id)
            .values(**updates)
            .returning(Campaign)
        )
        result = await self._session.execute(stmt)
        campaign: Campaign = result.scalar_one()
        await self._session.flush()
        return campaign

    async def update_status(
        self,
        campaign_id: UUID,
        status: CampaignStatus,
    ) -> Campaign:
        """Atualiza o status da campanha e retorna o objeto atualizado."""
        stmt = (
            update(Campaign)
            .where(Campaign.id == campaign_id)
            .values(status=status)
            .returning(Campaign)
        )
        result = await self._session.execute(stmt)
        campaign: Campaign = result.scalar_one()
        await self._session.flush()
        return campaign

    async def get_campaign_with_stats(
        self,
        campaign_id: UUID,
    ) -> Optional[CampaignStats]:
        """Busca campanha com contagens de convites e respostas via subqueries."""
        campaign_result = await self._session.execute(
            select(Campaign).where(Campaign.id == campaign_id)
        )
        campaign = campaign_result.scalar_one_or_none()
        if campaign is None:
            return None

        invitation_count_result = await self._session.execute(
            select(func.count(Invitation.id)).where(
                Invitation.campaign_id == campaign_id
            )
        )
        total_convites: int = invitation_count_result.scalar_one()

        response_count_result = await self._session.execute(
            select(func.count(SurveyResponse.id)).where(
                SurveyResponse.campaign_id == campaign_id
            )
        )
        total_respostas: int = response_count_result.scalar_one()

        return CampaignStats(
            campaign=campaign,
            total_convites=total_convites,
            total_respostas=total_respostas,
        )
