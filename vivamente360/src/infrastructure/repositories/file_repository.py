"""Repositório do módulo de File Assets (Módulo Storage).

Regra R2: Repositories só persistem — nenhuma regra de negócio aqui.
Regra R1: Type hints completos em todos os métodos.
Regra R4: list_by_context() retorna tupla (items, total) para paginação obrigatória.

O FileAsset armazena APENAS metadados. O conteúdo binário reside no Cloudflare R2
e nunca é manipulado por este repositório.
"""
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.file_asset import FileAsset

# Limite máximo de itens por página — Regra R4
_PAGE_SIZE_MAX: int = 100


class FileRepository(ABC):
    """Interface abstrata do repositório de FileAssets."""

    @abstractmethod
    async def create(
        self,
        company_id: UUID,
        contexto: str,
        nome_original: str,
        tamanho_bytes: int,
        content_type: str,
        storage_key: str,
        created_by: UUID,
        referencia_id: Optional[UUID] = None,
    ) -> FileAsset:
        """Persiste os metadados de um novo arquivo no banco.

        Args:
            company_id: UUID da empresa proprietária do arquivo.
            contexto: Contexto de uso (ex: 'checklist_evidencia', 'plano_acao').
            nome_original: Nome original do arquivo informado pelo usuário.
            tamanho_bytes: Tamanho do conteúdo em bytes.
            content_type: MIME type do arquivo.
            storage_key: Caminho no bucket R2 (gerado pelo r2_adapter).
            created_by: UUID do usuário que fez o upload.
            referencia_id: UUID do item relacionado (checklist_item, action_plan, etc.).

        Returns:
            FileAsset persistido com id gerado.
        """
        ...

    @abstractmethod
    async def get_by_id(self, file_id: UUID) -> Optional[FileAsset]:
        """Busca um FileAsset pelo UUID.

        Retorna None se não existir ou se o arquivo estiver marcado como deletado.
        """
        ...

    @abstractmethod
    async def list_by_context(
        self,
        company_id: UUID,
        contexto: str,
        referencia_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[FileAsset], int]:
        """Lista FileAssets ativos por contexto e empresa com paginação.

        Args:
            company_id: UUID da empresa (isolamento multi-tenant).
            contexto: Filtro por contexto de uso.
            referencia_id: Filtro opcional pelo ID do item relacionado.
            page: Número da página (1-indexed).
            page_size: Itens por página (máximo 100).

        Returns:
            Tupla (items, total) com os arquivos paginados e o total geral.
        """
        ...

    @abstractmethod
    async def soft_delete(self, file_id: UUID) -> bool:
        """Marca o FileAsset como deletado (soft delete).

        Seta deletado=True e deletado_em=NOW(). O arquivo físico no R2
        é removido de forma assíncrona por um worker de limpeza separado.

        Args:
            file_id: UUID do FileAsset a ser deletado.

        Returns:
            True se o arquivo foi encontrado e marcado, False se não existir.
        """
        ...


class SQLFileRepository(FileRepository):
    """Implementação SQLAlchemy 2.x do repositório de FileAssets."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        company_id: UUID,
        contexto: str,
        nome_original: str,
        tamanho_bytes: int,
        content_type: str,
        storage_key: str,
        created_by: UUID,
        referencia_id: Optional[UUID] = None,
    ) -> FileAsset:
        """Cria e persiste um novo FileAsset."""
        file_asset = FileAsset(
            company_id=company_id,
            contexto=contexto,
            referencia_id=referencia_id,
            nome_original=nome_original,
            tamanho_bytes=tamanho_bytes,
            content_type=content_type,
            storage_key=storage_key,
            created_by=created_by,
        )
        self._session.add(file_asset)
        await self._session.flush()
        return file_asset

    async def get_by_id(self, file_id: UUID) -> Optional[FileAsset]:
        """Busca FileAsset pelo UUID — ignora deletados."""
        result = await self._session.execute(
            select(FileAsset).where(
                FileAsset.id == file_id,
                FileAsset.deletado == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def list_by_context(
        self,
        company_id: UUID,
        contexto: str,
        referencia_id: Optional[UUID] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[FileAsset], int]:
        """Lista FileAssets ativos de um contexto com paginação."""
        page_size = min(page_size, _PAGE_SIZE_MAX)
        offset = (page - 1) * page_size

        base_stmt = select(FileAsset).where(
            FileAsset.company_id == company_id,
            FileAsset.contexto == contexto,
            FileAsset.deletado == False,  # noqa: E712
        )

        if referencia_id is not None:
            base_stmt = base_stmt.where(FileAsset.referencia_id == referencia_id)

        # Total sem paginação
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_result = await self._session.execute(count_stmt)
        total: int = total_result.scalar_one()

        # Itens paginados — mais recentes primeiro
        items_stmt = (
            base_stmt
            .order_by(FileAsset.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items_result = await self._session.execute(items_stmt)
        items: list[FileAsset] = list(items_result.scalars().all())

        return items, total

    async def soft_delete(self, file_id: UUID) -> bool:
        """Marca FileAsset como deletado logicamente."""
        result = await self._session.execute(
            update(FileAsset)
            .where(
                FileAsset.id == file_id,
                FileAsset.deletado == False,  # noqa: E712
            )
            .values(
                deletado=True,
                deletado_em=datetime.now(tz=timezone.utc),
            )
        )
        await self._session.flush()
        return result.rowcount > 0
