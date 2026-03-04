"""Router do módulo de File Assets — upload, download e exclusão de arquivos.

Regra R2: Controllers/Routers só validam entrada e delegam.
Regra R4: Endpoints de listagem têm paginação obrigatória (page + page_size).
Regra R1: Type hints completos em todos os parâmetros de função.

Regra inviolável de storage:
    Arquivos NUNCA são servidos diretamente pelo FastAPI.
    Acesso ao conteúdo ocorre APENAS via signed URLs geradas sob demanda.
    O conteúdo binário existe em memória APENAS durante o upload e é imediatamente
    repassado ao R2/S3 — nunca persiste no disco do servidor.

Endpoints implementados:
    POST   /files/upload              — upload de arquivo (multipart/form-data)
    GET    /files/{id}/url            — gera signed URL para download
    GET    /files                     — lista arquivos por contexto (paginado)
    DELETE /files/{id}                — soft delete do arquivo
"""
import math
import uuid
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database.session import get_db
from src.infrastructure.repositories.file_repository import SQLFileRepository
from src.infrastructure.storage.r2_adapter import (
    StorageAdapter,
    StorageContentTypeNotAllowed,
    StorageMagicBytesMismatch,
    StorageSizeLimitExceeded,
    build_storage_key,
    get_storage_adapter,
)
from src.presentation.dependencies.auth import CurrentUser, get_current_user
from src.presentation.schemas.file_schemas import (
    FileAssetResponse,
    FileDeleteResponse,
    FileListResponse,
    FilePaginationMeta,
    FileSignedUrlResponse,
)
from src.shared.config import settings
from src.shared.exceptions import ForbiddenError, NotFoundError

router: APIRouter = APIRouter(prefix="/files", tags=["files"])

# Contextos de arquivo permitidos para upload via API
_ALLOWED_CONTEXTS: frozenset[str] = frozenset(
    {
        "checklist_evidencia",
        "plano_acao",
    }
)

# Limites de paginação — Regra R4
_PAGE_SIZE_MAX: int = 100
_PAGE_SIZE_DEFAULT: int = 20


# ---------------------------------------------------------------------------
# POST /files/upload
# ---------------------------------------------------------------------------


@router.post(
    "/upload",
    response_model=FileAssetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload de arquivo de evidência",
    description=(
        "Faz upload de um arquivo para o Cloudflare R2 e persiste os metadados. "
        "Restrições: máximo 20 MB, tipos permitidos (imagens, PDF, documentos Office, ZIP). "
        "O conteúdo é validado via magic bytes — não apenas o MIME declarado. "
        "Retorna os metadados do arquivo; para acessar o conteúdo use GET /files/{id}/url."
    ),
)
async def upload_file(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[StorageAdapter, Depends(get_storage_adapter)],
    file: Annotated[UploadFile, File(description="Arquivo a ser enviado (máximo 20 MB).")],
    contexto: Annotated[
        str,
        Form(description="Contexto de uso: 'checklist_evidencia' ou 'plano_acao'."),
    ],
    referencia_id: Annotated[
        Optional[str],
        Form(description="UUID do item relacionado (opcional)."),
    ] = None,
) -> FileAssetResponse:
    """Valida e faz upload de arquivo para R2/S3.

    Args:
        current_user: Usuário autenticado (extrai company_id do JWT).
        db: Sessão assíncrona do banco de dados.
        storage: Adaptador de storage (R2StorageAdapter em produção).
        file: Arquivo recebido via multipart/form-data.
        contexto: Contexto do arquivo — valida contextos permitidos.
        referencia_id: UUID string do item relacionado (opcional).

    Returns:
        FileAssetResponse com metadados do arquivo criado.

    Raises:
        HTTP 400: Se contexto inválido, arquivo vazio ou tipo não permitido.
        HTTP 413: Se o arquivo exceder o limite de 20 MB.
        HTTP 422: Se o referencia_id não for um UUID válido.
    """
    # Validar contexto
    if contexto not in _ALLOWED_CONTEXTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Contexto inválido: {contexto!r}. "
                f"Aceitos: {sorted(_ALLOWED_CONTEXTS)}"
            ),
        )

    # Validar referencia_id se fornecido
    ref_id: Optional[uuid.UUID] = None
    if referencia_id:
        try:
            ref_id = uuid.UUID(referencia_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"referencia_id inválido: {referencia_id!r}. Esperado: UUID v4.",
            )

    # Ler conteúdo do arquivo em memória
    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo vazio. Envie um arquivo com conteúdo.",
        )

    # Gerar ID e chave do arquivo antes do upload
    file_id = uuid.uuid4()
    nome_original = file.filename or f"arquivo_{file_id}"
    content_type = file.content_type or "application/octet-stream"

    storage_key = build_storage_key(
        company_id=str(current_user.company_id),
        contexto=contexto,
        file_id=str(file_id),
        filename=nome_original,
    )

    # Upload com validação completa (tamanho + whitelist + magic bytes)
    try:
        await storage.upload(
            key=storage_key,
            data=content,
            content_type=content_type,
        )
    except StorageSizeLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=str(exc),
        )
    except StorageContentTypeNotAllowed as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except StorageMagicBytesMismatch as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    # Persistir metadados no banco
    repo = SQLFileRepository(db)
    file_asset = await repo.create(
        company_id=current_user.company_id,
        contexto=contexto,
        nome_original=nome_original,
        tamanho_bytes=len(content),
        content_type=content_type,
        storage_key=storage_key,
        created_by=current_user.user_id,
        referencia_id=ref_id,
    )
    await db.commit()
    await db.refresh(file_asset)

    return FileAssetResponse.model_validate(file_asset)


# ---------------------------------------------------------------------------
# GET /files/{file_id}/url
# ---------------------------------------------------------------------------


@router.get(
    "/{file_id}/url",
    response_model=FileSignedUrlResponse,
    status_code=status.HTTP_200_OK,
    summary="Gera URL assinada para download do arquivo",
    description=(
        "Gera uma URL temporária e assinada para acesso direto ao arquivo no Cloudflare R2. "
        f"A URL expira após {settings.STORAGE_SIGNED_URL_EXPIRES} segundos. "
        "Após expiração, solicite uma nova URL chamando este endpoint novamente."
    ),
)
async def get_file_url(
    file_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    storage: Annotated[StorageAdapter, Depends(get_storage_adapter)],
) -> FileSignedUrlResponse:
    """Gera URL assinada para download seguro de arquivo.

    Args:
        file_id: UUID do FileAsset.
        current_user: Usuário autenticado (RLS garante isolamento por empresa).
        db: Sessão assíncrona do banco de dados.
        storage: Adaptador de storage.

    Returns:
        FileSignedUrlResponse com URL temporária para download.

    Raises:
        HTTP 404: Se o arquivo não existir ou não pertencer à empresa do usuário.
    """
    repo = SQLFileRepository(db)
    file_asset = await repo.get_by_id(file_id)

    if file_asset is None or file_asset.company_id != current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Arquivo não encontrado: file_id={file_id}",
        )

    url = await storage.get_signed_url(
        key=file_asset.storage_key,
        expires_in=settings.STORAGE_SIGNED_URL_EXPIRES,
    )

    return FileSignedUrlResponse(
        file_id=file_asset.id,
        nome_original=file_asset.nome_original,
        content_type=file_asset.content_type,
        tamanho_bytes=file_asset.tamanho_bytes,
        url=url,
        expires_in_seconds=settings.STORAGE_SIGNED_URL_EXPIRES,
    )


# ---------------------------------------------------------------------------
# GET /files
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=FileListResponse,
    status_code=status.HTTP_200_OK,
    summary="Lista arquivos por contexto com paginação",
    description=(
        "Retorna os arquivos ativos da empresa filtrados por contexto. "
        "Use referencia_id para filtrar arquivos de um item específico "
        "(ex: evidências de um checklist_item ou plano de ação). "
        "Ordenação: mais recentes primeiro."
    ),
)
async def list_files(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    contexto: Annotated[
        str,
        Query(description="Contexto de uso: 'checklist_evidencia' ou 'plano_acao'."),
    ],
    referencia_id: Annotated[
        Optional[uuid.UUID],
        Query(description="Filtrar por item relacionado (opcional)."),
    ] = None,
    page: Annotated[
        int,
        Query(ge=1, description="Número da página (1-indexed)."),
    ] = 1,
    page_size: Annotated[
        int,
        Query(ge=1, le=_PAGE_SIZE_MAX, description="Itens por página (máximo 100)."),
    ] = _PAGE_SIZE_DEFAULT,
) -> FileListResponse:
    """Lista arquivos ativos com filtros e paginação.

    Args:
        current_user: Usuário autenticado (company_id extraído do JWT).
        db: Sessão assíncrona do banco de dados.
        contexto: Filtro obrigatório por contexto de uso.
        referencia_id: Filtro opcional pelo ID do item relacionado.
        page: Página da listagem (1-indexed, padrão 1).
        page_size: Itens por página (máximo 100, padrão 20).

    Returns:
        FileListResponse com items e metadados de paginação.
    """
    repo = SQLFileRepository(db)

    items, total = await repo.list_by_context(
        company_id=current_user.company_id,
        contexto=contexto,
        referencia_id=referencia_id,
        page=page,
        page_size=page_size,
    )

    pages = max(1, math.ceil(total / page_size)) if total > 0 else 0

    return FileListResponse(
        items=[FileAssetResponse.model_validate(item) for item in items],
        pagination=FilePaginationMeta(
            page=page,
            page_size=page_size,
            total=total,
            pages=pages,
        ),
    )


# ---------------------------------------------------------------------------
# DELETE /files/{file_id}
# ---------------------------------------------------------------------------


@router.delete(
    "/{file_id}",
    response_model=FileDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Remove logicamente um arquivo",
    description=(
        "Marca o arquivo como deletado (soft delete). "
        "O arquivo físico no Cloudflare R2 é removido de forma assíncrona por worker. "
        "Apenas o usuário que fez o upload ou um ADMIN/MANAGER pode deletar."
    ),
)
async def delete_file(
    file_id: uuid.UUID,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FileDeleteResponse:
    """Realiza soft delete do arquivo.

    Args:
        file_id: UUID do FileAsset a ser deletado.
        current_user: Usuário autenticado.
        db: Sessão assíncrona do banco de dados.

    Returns:
        FileDeleteResponse confirmando a exclusão.

    Raises:
        HTTP 403: Se o usuário não tiver permissão para deletar o arquivo.
        HTTP 404: Se o arquivo não existir ou já estiver deletado.
    """
    from src.domain.enums.user_role import UserRole

    repo = SQLFileRepository(db)
    file_asset = await repo.get_by_id(file_id)

    if file_asset is None or file_asset.company_id != current_user.company_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Arquivo não encontrado: file_id={file_id}",
        )

    # Apenas o criador ou ADMIN/MANAGER pode deletar
    is_owner = file_asset.created_by == current_user.user_id
    is_privileged = current_user.role in (UserRole.ADMIN, UserRole.MANAGER)

    if not is_owner and not is_privileged:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas o criador do arquivo ou ADMIN/MANAGER podem removê-lo.",
        )

    deleted = await repo.soft_delete(file_id)
    await db.commit()

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Arquivo não encontrado ou já removido: file_id={file_id}",
        )

    return FileDeleteResponse(
        file_id=file_id,
        deletado=True,
        mensagem="Arquivo marcado para remoção. O arquivo físico será deletado em breve.",
    )
