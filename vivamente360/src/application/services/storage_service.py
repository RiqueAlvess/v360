from uuid import UUID, uuid4

from src.domain.enums.file_contexto import FileContexto
from src.domain.enums.user_role import UserRole
from src.infrastructure.database.models.file_asset import FileAsset
from src.infrastructure.repositories.file_asset_repository import FileAssetRepository
from src.infrastructure.storage.r2_adapter import R2Adapter
from src.shared.exceptions import ForbiddenError, NotFoundError

MAX_FILE_SIZE_BYTES: int = 20 * 1024 * 1024  # 20 MB

SIGNED_URL_EXPIRY_SECONDS: int = 3600  # 1 hora

ALLOWED_MIME_TYPES: frozenset[str] = frozenset(
    {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "text/plain",
        "text/csv",
    }
)


class StorageService:
    """Orquestra upload, download e remoção de arquivos via Cloudflare R2.

    Nenhum módulo do sistema deve chamar R2Adapter diretamente.
    Todo acesso a arquivos passa por este service, que também gerencia
    os metadados persistidos na tabela file_assets.
    """

    def __init__(
        self,
        r2_adapter: R2Adapter,
        file_asset_repo: FileAssetRepository,
    ) -> None:
        self._r2 = r2_adapter
        self._repo = file_asset_repo

    def _build_r2_key(
        self,
        company_id: UUID,
        contexto: FileContexto,
        file_id: UUID,
        extension: str,
    ) -> str:
        """Constrói o caminho do objeto no bucket: company/{id}/{contexto}/{uuid}.ext"""
        return f"company/{company_id}/{contexto.value}/{file_id}{extension}"

    async def upload(
        self,
        company_id: UUID,
        user_id: UUID,
        filename: str,
        data: bytes,
        mime_type: str,
        contexto: FileContexto,
        referencia_id: UUID | None = None,
    ) -> tuple[FileAsset, str]:
        """Faz upload do arquivo para R2 e persiste os metadados no banco.

        Returns:
            Tupla (FileAsset com metadados, signed_url válida por 1h).
        """
        file_id = uuid4()
        extension = f".{filename.rsplit('.', 1)[-1].lower()}" if "." in filename else ""
        r2_key = self._build_r2_key(company_id, contexto, file_id, extension)

        await self._r2.upload(r2_key, data, mime_type)

        asset = FileAsset(
            id=file_id,
            company_id=company_id,
            uploaded_by=user_id,
            r2_key=r2_key,
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(data),
            contexto=contexto.value,
            referencia_id=referencia_id,
        )
        await self._repo.create(asset)

        signed_url = await self._r2.signed_url(r2_key, SIGNED_URL_EXPIRY_SECONDS)
        return asset, signed_url

    async def get_signed_url(
        self,
        asset_id: UUID,
        company_id: UUID,
    ) -> str:
        """Gera nova signed URL (1h) para um arquivo existente.

        Raises:
            NotFoundError: se o arquivo não existe ou foi deletado.
            ForbiddenError: se o arquivo pertence a outra empresa.
        """
        asset = await self._repo.get_by_id(asset_id)
        if asset is None:
            raise NotFoundError("Arquivo")

        if asset.company_id != company_id:
            raise ForbiddenError("Sem permissão para acessar este arquivo")

        return await self._r2.signed_url(asset.r2_key, SIGNED_URL_EXPIRY_SECONDS)

    async def delete(
        self,
        asset_id: UUID,
        company_id: UUID,
        user_id: UUID,
        role: UserRole,
    ) -> None:
        """Remove o arquivo do R2 e faz soft-delete dos metadados no banco.

        Apenas o uploader original ou um usuário ADMIN pode deletar.

        Raises:
            NotFoundError: se o arquivo não existe ou foi deletado.
            ForbiddenError: se o solicitante não tem permissão para deletar.
        """
        asset = await self._repo.get_by_id(asset_id)
        if asset is None:
            raise NotFoundError("Arquivo")

        if asset.company_id != company_id:
            raise ForbiddenError("Sem permissão para deletar este arquivo")

        is_admin = role == UserRole.ADMIN
        if not is_admin and asset.uploaded_by != user_id:
            raise ForbiddenError("Apenas o uploader original ou admin pode deletar este arquivo")

        await self._r2.delete(asset.r2_key)
        await self._repo.soft_delete(asset_id)
