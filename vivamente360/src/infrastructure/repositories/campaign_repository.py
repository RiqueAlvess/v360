"""Repositório de campanhas de avaliação psicossocial.

Regra R2: Repositories só persistem — nenhuma regra de negócio aqui.
Regra R1: Type hints completos em todos os métodos.
Regra R4: list_by_company() retorna tupla (items, total) para paginação.
"""
import uuid
from abc import ABC, abstractmethod
from datetime import date
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.campaign import Campaign

# Limite máximo de itens por página — Regra R4
_PAGE_SIZE_MAX: int = 100


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
