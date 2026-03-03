"""Repositório do módulo de Plano de Ação.

Regra R2: Repositories só persistem — nenhuma regra de negócio aqui.
Regra R1: Type hints completos em todos os métodos.
Regra R4: list_by_campaign() retorna tupla (items, total) para paginação obrigatória.
"""
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.enums.action_plan_status import ActionPlanStatus
from src.domain.enums.nivel_risco import NivelRisco
from src.infrastructure.database.models.action_plan import ActionPlan
from src.infrastructure.database.models.file_asset import FileAsset

# Constante para o contexto de evidência de plano de ação
CONTEXTO_PLANO_ACAO: str = "plano_acao"

# Limite máximo de itens por página — Regra R4
_PAGE_SIZE_MAX: int = 100


class ActionPlanRepository(ABC):
    """Interface abstrata do repositório de Plano de Ação."""

    @abstractmethod
    async def list_by_campaign(
        self,
        campaign_id: UUID,
        status: Optional[ActionPlanStatus] = None,
        dimensao: Optional[str] = None,
        unidade_id: Optional[UUID] = None,
        nivel_risco: Optional[NivelRisco] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ActionPlan], int]:
        """Retorna os planos de uma campanha com filtros opcionais e paginação.

        Args:
            campaign_id: UUID da campanha.
            status: Filtro opcional por status do plano.
            dimensao: Filtro opcional por dimensão HSE-IT vinculada.
            unidade_id: Filtro opcional por unidade organizacional.
            nivel_risco: Filtro opcional por nível de risco.
            page: Número da página (1-indexed).
            page_size: Quantidade de itens por página (máximo 100).

        Returns:
            Tupla (items, total) com os planos paginados e o total geral.
        """
        ...

    @abstractmethod
    async def get_by_id(self, plan_id: UUID) -> Optional[ActionPlan]:
        """Busca um plano de ação pelo seu UUID.

        Returns:
            O ActionPlan encontrado ou None se não existir.
        """
        ...

    @abstractmethod
    async def create(
        self,
        campaign_id: UUID,
        company_id: UUID,
        titulo: str,
        descricao: str,
        nivel_risco: NivelRisco,
        prazo: Any,
        created_by: UUID,
        dimensao: Optional[str] = None,
        unidade_id: Optional[UUID] = None,
        setor_id: Optional[UUID] = None,
        responsavel_id: Optional[UUID] = None,
        responsavel_externo: Optional[str] = None,
    ) -> ActionPlan:
        """Cria e persiste um novo plano de ação.

        Returns:
            O ActionPlan criado com id gerado.
        """
        ...

    @abstractmethod
    async def update(
        self,
        plan_id: UUID,
        titulo: Optional[str] = None,
        descricao: Optional[str] = None,
        dimensao: Optional[str] = None,
        unidade_id: Optional[UUID] = None,
        setor_id: Optional[UUID] = None,
        responsavel_id: Optional[UUID] = None,
        responsavel_externo: Optional[str] = None,
        nivel_risco: Optional[NivelRisco] = None,
        prazo: Optional[Any] = None,
    ) -> ActionPlan:
        """Atualiza campos parciais de um plano de ação (PATCH).

        Apenas os campos não-None são atualizados.

        Returns:
            O ActionPlan atualizado.
        """
        ...

    @abstractmethod
    async def update_status(
        self,
        plan_id: UUID,
        status: ActionPlanStatus,
        concluido_em: Optional[datetime] = None,
    ) -> ActionPlan:
        """Atualiza o status de um plano de ação.

        Quando status='concluido', concluido_em deve ser informado.

        Returns:
            O ActionPlan com status atualizado.
        """
        ...

    @abstractmethod
    async def get_resumo_por_status(self, campaign_id: UUID) -> dict[str, Any]:
        """Calcula o resumo de planos por status para uma campanha.

        Returns:
            Dict com 'total' e 'por_status' contendo a contagem por status.
        """
        ...

    @abstractmethod
    async def get_evidencias(self, plan_id: UUID) -> list[FileAsset]:
        """Retorna as evidências (file_assets) vinculadas a um plano de ação."""
        ...

    @abstractmethod
    async def add_evidencia(
        self,
        plan_id: UUID,
        company_id: UUID,
        nome_original: str,
        tamanho_bytes: int,
        content_type: str,
        storage_key: str,
        created_by: Optional[UUID] = None,
    ) -> FileAsset:
        """Registra metadados de uma evidência vinculada ao plano de ação."""
        ...


class SQLActionPlanRepository(ActionPlanRepository):
    """Implementação SQLAlchemy 2.x do repositório de Plano de Ação."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_by_campaign(
        self,
        campaign_id: UUID,
        status: Optional[ActionPlanStatus] = None,
        dimensao: Optional[str] = None,
        unidade_id: Optional[UUID] = None,
        nivel_risco: Optional[NivelRisco] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ActionPlan], int]:
        """Retorna planos paginados da campanha com filtros opcionais."""
        page_size = min(page_size, _PAGE_SIZE_MAX)
        offset = (page - 1) * page_size

        base_stmt = select(ActionPlan).where(ActionPlan.campaign_id == campaign_id)

        if status is not None:
            base_stmt = base_stmt.where(ActionPlan.status == status)

        if dimensao is not None:
            base_stmt = base_stmt.where(ActionPlan.dimensao == dimensao)

        if unidade_id is not None:
            base_stmt = base_stmt.where(ActionPlan.unidade_id == unidade_id)

        if nivel_risco is not None:
            base_stmt = base_stmt.where(ActionPlan.nivel_risco == nivel_risco)

        # Contagem total para paginação
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_result = await self._session.execute(count_stmt)
        total: int = total_result.scalar_one()

        # Query paginada, ordenada por prazo ascendente e criação
        items_stmt = (
            base_stmt
            .order_by(ActionPlan.prazo.asc(), ActionPlan.created_at.asc())
            .offset(offset)
            .limit(page_size)
        )
        items_result = await self._session.execute(items_stmt)
        items: list[ActionPlan] = list(items_result.scalars().all())

        return items, total

    async def get_by_id(self, plan_id: UUID) -> Optional[ActionPlan]:
        """Busca plano pelo UUID, retorna None se não existir."""
        result = await self._session.execute(
            select(ActionPlan).where(ActionPlan.id == plan_id)
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        campaign_id: UUID,
        company_id: UUID,
        titulo: str,
        descricao: str,
        nivel_risco: NivelRisco,
        prazo: Any,
        created_by: UUID,
        dimensao: Optional[str] = None,
        unidade_id: Optional[UUID] = None,
        setor_id: Optional[UUID] = None,
        responsavel_id: Optional[UUID] = None,
        responsavel_externo: Optional[str] = None,
    ) -> ActionPlan:
        """Cria e persiste um novo plano de ação com status inicial 'pendente'."""
        plan = ActionPlan(
            id=uuid.uuid4(),
            campaign_id=campaign_id,
            company_id=company_id,
            titulo=titulo,
            descricao=descricao,
            dimensao=dimensao,
            unidade_id=unidade_id,
            setor_id=setor_id,
            responsavel_id=responsavel_id,
            responsavel_externo=responsavel_externo,
            nivel_risco=nivel_risco,
            status=ActionPlanStatus.PENDENTE,
            prazo=prazo,
            created_by=created_by,
        )
        self._session.add(plan)
        await self._session.flush()
        return plan

    async def update(
        self,
        plan_id: UUID,
        titulo: Optional[str] = None,
        descricao: Optional[str] = None,
        dimensao: Optional[str] = None,
        unidade_id: Optional[UUID] = None,
        setor_id: Optional[UUID] = None,
        responsavel_id: Optional[UUID] = None,
        responsavel_externo: Optional[str] = None,
        nivel_risco: Optional[NivelRisco] = None,
        prazo: Optional[Any] = None,
    ) -> ActionPlan:
        """Atualiza apenas os campos fornecidos (PATCH parcial)."""
        values: dict[str, Any] = {}

        if titulo is not None:
            values["titulo"] = titulo
        if descricao is not None:
            values["descricao"] = descricao
        if dimensao is not None:
            values["dimensao"] = dimensao
        if unidade_id is not None:
            values["unidade_id"] = unidade_id
        if setor_id is not None:
            values["setor_id"] = setor_id
        if responsavel_id is not None:
            values["responsavel_id"] = responsavel_id
        if responsavel_externo is not None:
            values["responsavel_externo"] = responsavel_externo
        if nivel_risco is not None:
            values["nivel_risco"] = nivel_risco
        if prazo is not None:
            values["prazo"] = prazo

        stmt = (
            update(ActionPlan)
            .where(ActionPlan.id == plan_id)
            .values(**values)
            .returning(ActionPlan)
        )
        result = await self._session.execute(stmt)
        plan: ActionPlan = result.scalar_one()
        await self._session.flush()
        return plan

    async def update_status(
        self,
        plan_id: UUID,
        status: ActionPlanStatus,
        concluido_em: Optional[datetime] = None,
    ) -> ActionPlan:
        """Atualiza o status do plano. Se concluido, seta concluido_em."""
        values: dict[str, Any] = {"status": status}
        if concluido_em is not None:
            values["concluido_em"] = concluido_em

        stmt = (
            update(ActionPlan)
            .where(ActionPlan.id == plan_id)
            .values(**values)
            .returning(ActionPlan)
        )
        result = await self._session.execute(stmt)
        plan: ActionPlan = result.scalar_one()
        await self._session.flush()
        return plan

    async def get_resumo_por_status(self, campaign_id: UUID) -> dict[str, Any]:
        """Calcula resumo via agregação SQL — sem cálculo no Python."""
        stmt = (
            select(
                ActionPlan.status,
                func.count(ActionPlan.id).label("quantidade"),
            )
            .where(ActionPlan.campaign_id == campaign_id)
            .group_by(ActionPlan.status)
        )
        result = await self._session.execute(stmt)
        rows = result.all()

        por_status: dict[str, int] = {
            ActionPlanStatus.PENDENTE.value: 0,
            ActionPlanStatus.EM_ANDAMENTO.value: 0,
            ActionPlanStatus.CONCLUIDO.value: 0,
            ActionPlanStatus.CANCELADO.value: 0,
        }
        total: int = 0

        for row in rows:
            status_value: str = row.status.value if hasattr(row.status, "value") else row.status
            quantidade: int = row.quantidade
            if status_value in por_status:
                por_status[status_value] = quantidade
            total += quantidade

        return {"total": total, "por_status": por_status}

    async def get_evidencias(self, plan_id: UUID) -> list[FileAsset]:
        """Retorna evidências ativas vinculadas ao plano, ordenadas por data."""
        result = await self._session.execute(
            select(FileAsset)
            .where(
                FileAsset.referencia_id == plan_id,
                FileAsset.contexto == CONTEXTO_PLANO_ACAO,
                FileAsset.deletado.is_(False),
            )
            .order_by(FileAsset.created_at.asc())
        )
        return list(result.scalars().all())

    async def add_evidencia(
        self,
        plan_id: UUID,
        company_id: UUID,
        nome_original: str,
        tamanho_bytes: int,
        content_type: str,
        storage_key: str,
        created_by: Optional[UUID] = None,
    ) -> FileAsset:
        """Cria e persiste um registro de file_asset para a evidência do plano."""
        asset = FileAsset(
            id=uuid.uuid4(),
            company_id=company_id,
            contexto=CONTEXTO_PLANO_ACAO,
            referencia_id=plan_id,
            nome_original=nome_original,
            tamanho_bytes=tamanho_bytes,
            content_type=content_type,
            storage_key=storage_key,
            created_by=created_by,
        )
        self._session.add(asset)
        await self._session.flush()
        return asset
