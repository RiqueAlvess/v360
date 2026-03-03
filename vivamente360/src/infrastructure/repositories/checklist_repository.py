"""Repositório do módulo de Checklist NR-1.

Regra R2: Repositories só persistem — nenhuma regra de negócio aqui.
Regra R1: Type hints completos em todos os métodos.
Regra R4: get_by_campaign() retorna tupla (items, total) para paginação obrigatória.
"""
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.checklist_item import ChecklistItem
from src.infrastructure.database.models.checklist_template import ChecklistTemplate
from src.infrastructure.database.models.file_asset import (
    CONTEXTO_CHECKLIST_EVIDENCIA,
    FileAsset,
)

# Limite máximo de itens por página — Regra R4
_PAGE_SIZE_MAX: int = 100


class ChecklistRepository(ABC):
    """Interface abstrata do repositório de Checklist NR-1."""

    @abstractmethod
    async def get_by_campaign(
        self,
        campaign_id: UUID,
        categoria: Optional[str] = None,
        concluido: Optional[bool] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[ChecklistItem], int]:
        """Retorna os itens do checklist de uma campanha com paginação.

        Args:
            campaign_id: UUID da campanha.
            categoria: Filtro opcional por categoria NR-1.
            concluido: Filtro opcional por status de conclusão.
            page: Número da página (1-indexed).
            page_size: Quantidade de itens por página (máximo 100).

        Returns:
            Tupla (items, total) com os itens paginados e o total geral.
        """
        ...

    @abstractmethod
    async def get_item_by_id(self, item_id: UUID) -> Optional[ChecklistItem]:
        """Busca um item do checklist pelo seu UUID."""
        ...

    @abstractmethod
    async def toggle_item(
        self,
        item_id: UUID,
        concluido: bool,
        user_id: UUID,
        observacao: Optional[str] = None,
    ) -> ChecklistItem:
        """Alterna o estado de conclusão de um item.

        Registra concluido_em e concluido_por quando concluido=True.
        Limpa concluido_em e concluido_por quando concluido=False.

        Args:
            item_id: UUID do item a ser atualizado.
            concluido: Novo estado de conclusão.
            user_id: UUID do usuário que realizou a ação.
            observacao: Observação opcional registrada junto à alteração.

        Returns:
            O item atualizado com os novos valores.
        """
        ...

    @abstractmethod
    async def get_progresso(self, campaign_id: UUID) -> dict[str, Any]:
        """Calcula o progresso do checklist para uma campanha.

        Args:
            campaign_id: UUID da campanha.

        Returns:
            Dict com total, concluidos e percentual (0.0 a 100.0).
        """
        ...

    @abstractmethod
    async def get_all_templates(self) -> list[ChecklistTemplate]:
        """Retorna todos os templates canônicos NR-1 ordenados por `ordem`."""
        ...

    @abstractmethod
    async def create_items_from_templates(
        self,
        campaign_id: UUID,
        company_id: UUID,
    ) -> list[ChecklistItem]:
        """Cria os itens do checklist a partir de todos os templates ativos.

        Chamado pelo CampaignService durante a criação de uma nova campanha.
        Usa INSERT ... ON CONFLICT DO NOTHING para garantir idempotência.

        Args:
            campaign_id: UUID da campanha recém-criada.
            company_id: UUID da empresa dona da campanha.

        Returns:
            Lista de ChecklistItem criados.
        """
        ...

    @abstractmethod
    async def get_evidencias(self, item_id: UUID) -> list[FileAsset]:
        """Retorna as evidências (file_assets) vinculadas a um item do checklist."""
        ...

    @abstractmethod
    async def add_evidencia(
        self,
        item_id: UUID,
        company_id: UUID,
        nome_original: str,
        tamanho_bytes: int,
        content_type: str,
        storage_key: str,
        created_by: Optional[UUID] = None,
    ) -> FileAsset:
        """Registra metadados de uma evidência vinculada ao item do checklist."""
        ...

    @abstractmethod
    async def delete_evidencia(self, file_id: UUID) -> bool:
        """Soft delete de uma evidência (file_asset).

        Returns:
            True se o arquivo foi encontrado e marcado como deletado, False caso contrário.
        """
        ...


class SQLChecklistRepository(ChecklistRepository):
    """Implementação SQLAlchemy 2.x do repositório de Checklist NR-1."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_campaign(
        self,
        campaign_id: UUID,
        categoria: Optional[str] = None,
        concluido: Optional[bool] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[ChecklistItem], int]:
        """Retorna itens paginados do checklist com filtros opcionais."""
        page_size = min(page_size, _PAGE_SIZE_MAX)
        offset = (page - 1) * page_size

        # Query base com join no template (lazy="joined" já carrega, mas explicitamos)
        base_stmt = (
            select(ChecklistItem)
            .where(ChecklistItem.campaign_id == campaign_id)
            .join(ChecklistTemplate, ChecklistItem.template_id == ChecklistTemplate.id)
        )

        if categoria is not None:
            base_stmt = base_stmt.where(ChecklistTemplate.categoria == categoria)

        if concluido is not None:
            base_stmt = base_stmt.where(ChecklistItem.concluido == concluido)

        # Contagem total para paginação
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_result = await self._session.execute(count_stmt)
        total: int = total_result.scalar_one()

        # Query paginada, ordenada por template.ordem
        items_stmt = (
            base_stmt
            .order_by(ChecklistTemplate.ordem.asc(), ChecklistItem.created_at.asc())
            .offset(offset)
            .limit(page_size)
        )
        items_result = await self._session.execute(items_stmt)
        items: list[ChecklistItem] = list(items_result.scalars().all())

        return items, total

    async def get_item_by_id(self, item_id: UUID) -> Optional[ChecklistItem]:
        """Busca item pelo UUID, retorna None se não existir."""
        result = await self._session.execute(
            select(ChecklistItem).where(ChecklistItem.id == item_id)
        )
        return result.scalar_one_or_none()

    async def toggle_item(
        self,
        item_id: UUID,
        concluido: bool,
        user_id: UUID,
        observacao: Optional[str] = None,
    ) -> ChecklistItem:
        """Alterna conclusão do item e registra metadados de auditoria."""
        now: Optional[datetime] = datetime.now(tz=timezone.utc) if concluido else None
        concluded_by: Optional[UUID] = user_id if concluido else None

        stmt = (
            update(ChecklistItem)
            .where(ChecklistItem.id == item_id)
            .values(
                concluido=concluido,
                concluido_em=now,
                concluido_por=concluded_by,
                observacao=observacao,
            )
            .returning(ChecklistItem)
        )
        result = await self._session.execute(stmt)
        item: ChecklistItem = result.scalar_one()
        await self._session.flush()
        return item

    async def get_progresso(self, campaign_id: UUID) -> dict[str, Any]:
        """Calcula progresso via agregação SQL — sem cálculo no Python."""
        stmt = select(
            func.count(ChecklistItem.id).label("total"),
            func.count(ChecklistItem.id)
            .filter(ChecklistItem.concluido.is_(True))
            .label("concluidos"),
        ).where(ChecklistItem.campaign_id == campaign_id)

        result = await self._session.execute(stmt)
        row = result.one()
        total: int = row.total or 0
        concluidos: int = row.concluidos or 0
        percentual: float = round((concluidos / total * 100), 1) if total > 0 else 0.0

        return {"total": total, "concluidos": concluidos, "percentual": percentual}

    async def get_all_templates(self) -> list[ChecklistTemplate]:
        """Retorna todos os templates ordenados por campo `ordem`."""
        result = await self._session.execute(
            select(ChecklistTemplate).order_by(ChecklistTemplate.ordem.asc())
        )
        return list(result.scalars().all())

    async def create_items_from_templates(
        self,
        campaign_id: UUID,
        company_id: UUID,
    ) -> list[ChecklistItem]:
        """Cria um ChecklistItem para cada template existente.

        Idempotente via INSERT ... ON CONFLICT DO NOTHING: se um template já
        tiver um item criado para esta campanha (constraint única campaign_id,
        template_id), o registro é ignorado silenciosamente — sem IntegrityError.
        Retorna todos os itens da campanha ao final, incluindo pré-existentes.

        Args:
            campaign_id: UUID da campanha recém-criada.
            company_id: UUID da empresa dona da campanha.

        Returns:
            Lista de todos os ChecklistItem da campanha após a operação.
        """
        templates: list[ChecklistTemplate] = await self.get_all_templates()

        if not templates:
            return []

        values: list[dict[str, Any]] = [
            {
                "id": uuid.uuid4(),
                "campaign_id": campaign_id,
                "template_id": template.id,
                "company_id": company_id,
                "concluido": False,
            }
            for template in templates
        ]

        # ON CONFLICT DO NOTHING garante idempotência via unique constraint
        stmt = (
            pg_insert(ChecklistItem)
            .values(values)
            .on_conflict_do_nothing(
                constraint="uq_checklist_items_campaign_template",
            )
        )
        await self._session.execute(stmt)
        await self._session.flush()

        # Retorna todos os itens da campanha (inseridos agora ou pré-existentes)
        result = await self._session.execute(
            select(ChecklistItem)
            .where(ChecklistItem.campaign_id == campaign_id)
            .order_by(ChecklistItem.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_evidencias(self, item_id: UUID) -> list[FileAsset]:
        """Retorna evidências ativas vinculadas ao item, ordenadas por data de criação."""
        result = await self._session.execute(
            select(FileAsset)
            .where(
                FileAsset.referencia_id == item_id,
                FileAsset.contexto == CONTEXTO_CHECKLIST_EVIDENCIA,
                FileAsset.deletado.is_(False),
            )
            .order_by(FileAsset.created_at.asc())
        )
        return list(result.scalars().all())

    async def add_evidencia(
        self,
        item_id: UUID,
        company_id: UUID,
        nome_original: str,
        tamanho_bytes: int,
        content_type: str,
        storage_key: str,
        created_by: Optional[UUID] = None,
    ) -> FileAsset:
        """Cria e persiste um registro de file_asset para a evidência."""
        asset = FileAsset(
            id=uuid.uuid4(),
            company_id=company_id,
            contexto=CONTEXTO_CHECKLIST_EVIDENCIA,
            referencia_id=item_id,
            nome_original=nome_original,
            tamanho_bytes=tamanho_bytes,
            content_type=content_type,
            storage_key=storage_key,
            created_by=created_by,
        )
        self._session.add(asset)
        await self._session.flush()
        return asset

    async def delete_evidencia(self, file_id: UUID) -> bool:
        """Soft delete: marca o file_asset como deletado sem remover do banco."""
        now = datetime.now(tz=timezone.utc)
        stmt = (
            update(FileAsset)
            .where(FileAsset.id == file_id, FileAsset.deletado.is_(False))
            .values(deletado=True, deletado_em=now)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount > 0
