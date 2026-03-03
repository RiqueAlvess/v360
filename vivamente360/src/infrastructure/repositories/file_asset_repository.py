from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.models.file_asset import FileAsset


class FileAssetRepository(ABC):
    """Interface abstrata para persistência de metadados de arquivos."""

    @abstractmethod
    async def create(self, asset: FileAsset) -> FileAsset:
        """Persiste um novo registro de file_asset e retorna o objeto com id preenchido."""
        ...

    @abstractmethod
    async def get_by_id(self, asset_id: UUID) -> Optional[FileAsset]:
        """Busca um file_asset não-deletado pelo UUID primário."""
        ...

    @abstractmethod
    async def list_by_referencia(
        self,
        referencia_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[FileAsset], int]:
        """Lista arquivos por referencia_id com paginação. Retorna (items, total)."""
        ...

    @abstractmethod
    async def soft_delete(self, asset_id: UUID) -> None:
        """Marca o arquivo como deletado sem removê-lo do banco."""
        ...


class SQLFileAssetRepository(FileAssetRepository):
    """Implementação SQLAlchemy 2.x do repositório de file_assets."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, asset: FileAsset) -> FileAsset:
        self._session.add(asset)
        await self._session.flush()
        return asset

    async def get_by_id(self, asset_id: UUID) -> Optional[FileAsset]:
        result = await self._session.execute(
            select(FileAsset).where(
                FileAsset.id == asset_id,
                FileAsset.deletado.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def list_by_referencia(
        self,
        referencia_id: UUID,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[FileAsset], int]:
        base_filter = (
            FileAsset.referencia_id == referencia_id,
            FileAsset.deletado.is_(False),
        )

        count_result = await self._session.execute(
            select(func.count()).select_from(FileAsset).where(*base_filter)
        )
        total: int = count_result.scalar_one()

        offset = (page - 1) * page_size
        items_result = await self._session.execute(
            select(FileAsset)
            .where(*base_filter)
            .order_by(FileAsset.created_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        items: List[FileAsset] = list(items_result.scalars().all())

        return items, total

    async def soft_delete(self, asset_id: UUID) -> None:
        await self._session.execute(
            update(FileAsset)
            .where(FileAsset.id == asset_id)
            .values(deletado=True)
        )
