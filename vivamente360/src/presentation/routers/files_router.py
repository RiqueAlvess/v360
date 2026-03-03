from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.services.storage_service import (
    ALLOWED_MIME_TYPES,
    MAX_FILE_SIZE_BYTES,
    StorageService,
)
from src.domain.enums.file_contexto import FileContexto
from src.infrastructure.database.session import get_db
from src.infrastructure.repositories.file_asset_repository import SQLFileAssetRepository
from src.infrastructure.storage.r2_adapter import R2Adapter
from src.presentation.dependencies.auth import CurrentUser, get_current_user
from src.presentation.schemas.file_schemas import FileUploadResponse, SignedUrlResponse
from src.shared.config import settings
from src.shared.exceptions import ForbiddenError, NotFoundError

router: APIRouter = APIRouter(prefix="/files", tags=["files"])


def _build_storage_service(db: AsyncSession) -> StorageService:
    """Constrói StorageService com suas dependências concretas."""
    adapter = R2Adapter(
        account_id=settings.CF_R2_ACCOUNT_ID,
        access_key=settings.CF_R2_ACCESS_KEY,
        secret_key=settings.CF_R2_SECRET_KEY,
        bucket_name=settings.CF_R2_BUCKET,
    )
    return StorageService(
        r2_adapter=adapter,
        file_asset_repo=SQLFileAssetRepository(db),
    )


@router.post(
    "/upload",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload de arquivo",
    description=(
        "Recebe um arquivo via multipart/form-data, valida tipo e tamanho, "
        "faz upload para o Cloudflare R2 e retorna uma signed URL válida por 1h. "
        "O arquivo nunca é servido diretamente pelo FastAPI."
    ),
)
async def upload_file(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
    contexto: FileContexto = Form(...),
    referencia_id: Optional[UUID] = Form(None),
) -> FileUploadResponse:
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Tipo de arquivo não permitido: {file.content_type}. "
                f"Tipos aceitos: {', '.join(sorted(ALLOWED_MIME_TYPES))}"
            ),
        )

    data = await file.read()

    if len(data) > MAX_FILE_SIZE_BYTES:
        size_mb = len(data) / (1024 * 1024)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Arquivo muito grande: {size_mb:.1f}MB. Tamanho máximo permitido: 20MB.",
        )

    service = _build_storage_service(db)
    asset, signed_url = await service.upload(
        company_id=current_user.company_id,
        user_id=current_user.user_id,
        filename=file.filename or "arquivo",
        data=data,
        mime_type=file.content_type or "application/octet-stream",
        contexto=contexto,
        referencia_id=referencia_id,
    )
    await db.commit()

    return FileUploadResponse(
        file_id=asset.id,
        filename=asset.filename,
        size_bytes=asset.size_bytes,
        signed_url=signed_url,
    )


@router.get(
    "/{file_id}/url",
    response_model=SignedUrlResponse,
    status_code=status.HTTP_200_OK,
    summary="Obter URL de download",
    description="Gera nova signed URL (válida por 1h) para download do arquivo via R2.",
)
async def get_file_url(
    file_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SignedUrlResponse:
    service = _build_storage_service(db)
    try:
        url = await service.get_signed_url(
            asset_id=file_id,
            company_id=current_user.company_id,
        )
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=exc.detail
        ) from exc
    except ForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=exc.detail
        ) from exc

    return SignedUrlResponse(signed_url=url)


@router.delete(
    "/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deletar arquivo",
    description=(
        "Soft-delete no banco + remoção do objeto no R2. "
        "Apenas o uploader original ou um admin pode deletar."
    ),
)
async def delete_file(
    file_id: UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    service = _build_storage_service(db)
    try:
        await service.delete(
            asset_id=file_id,
            company_id=current_user.company_id,
            user_id=current_user.user_id,
            role=current_user.role,
        )
    except NotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=exc.detail
        ) from exc
    except ForbiddenError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=exc.detail
        ) from exc

    await db.commit()
