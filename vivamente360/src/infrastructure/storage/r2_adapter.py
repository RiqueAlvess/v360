"""Adaptador para Cloudflare R2 / S3-compatible storage.

Regra R6: Este é o ÚNICO arquivo que importa o SDK boto3 para operações de storage.
Nenhum outro módulo pode realizar chamadas S3/R2 diretamente.

REGRAS DE SEGURANÇA:
    - Validação de magic bytes antes de aceitar qualquer upload (não apenas MIME declarado).
    - Limite máximo de STORAGE_MAX_FILE_SIZE (20 MB) por arquivo.
    - Whitelist de tipos de conteúdo permitidos — rejeita executáveis e scripts.
    - Arquivos nunca servidos diretamente pelo FastAPI — apenas via signed URLs temporárias.
    - Soft delete: o campo `deletado` no banco marca exclusão lógica;
      a remoção física no R2 ocorre de forma assíncrona por worker de limpeza.
"""
import asyncio
import logging
import os
import uuid
from abc import ABC, abstractmethod
from typing import Optional

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from src.shared.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Whitelist de tipos de conteúdo permitidos
# ---------------------------------------------------------------------------

ALLOWED_CONTENT_TYPES: frozenset[str] = frozenset(
    {
        # Imagens
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "image/svg+xml",
        # Documentos
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.ms-excel",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-powerpoint",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        # Texto
        "text/plain",
        "text/csv",
        # Comprimidos
        "application/zip",
        "application/x-zip-compressed",
    }
)

# ---------------------------------------------------------------------------
# Magic bytes para validação real de tipo de arquivo (não apenas MIME declarado)
# ---------------------------------------------------------------------------

# Formato: (magic_bytes_prefix, tamanho_a_verificar)
_MAGIC_SIGNATURES: dict[bytes, str] = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
    b"RIFF": "image/webp",  # Prefixo parcial — verificação adicional abaixo
    b"%PDF": "application/pdf",
    b"PK\x03\x04": "application/zip",  # ZIP + OOXML (docx, xlsx, pptx)
    b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1": "application/msword",  # OLE2 (doc, xls, ppt)
}


def _detect_mime_from_magic(data: bytes) -> Optional[str]:
    """Detecta tipo MIME via inspeção dos bytes iniciais do arquivo.

    Args:
        data: Bytes iniciais do arquivo (mínimo 12 bytes recomendado).

    Returns:
        String MIME detectada ou None se desconhecida.
    """
    for signature, mime_type in _MAGIC_SIGNATURES.items():
        if data.startswith(signature):
            # Verificação adicional para WEBP (RIFF....WEBP)
            if signature == b"RIFF" and len(data) >= 12:
                if data[8:12] != b"WEBP":
                    continue
            return mime_type
    return None


# ---------------------------------------------------------------------------
# Exceções do módulo de storage
# ---------------------------------------------------------------------------


class StorageError(Exception):
    """Erro base para operações de storage."""


class StorageSizeLimitExceeded(StorageError):
    """Levantada quando o arquivo ultrapassa STORAGE_MAX_FILE_SIZE."""

    def __init__(self, size_bytes: int, limit_bytes: int) -> None:
        super().__init__(
            f"Arquivo excede o limite de {limit_bytes // (1024 * 1024)} MB "
            f"(recebido: {size_bytes // (1024 * 1024)} MB)."
        )
        self.size_bytes = size_bytes
        self.limit_bytes = limit_bytes


class StorageContentTypeNotAllowed(StorageError):
    """Levantada quando o tipo de conteúdo não está na whitelist."""

    def __init__(self, content_type: str) -> None:
        super().__init__(
            f"Tipo de arquivo não permitido: {content_type!r}. "
            f"Formatos aceitos: imagens, PDF, documentos Office e ZIP."
        )
        self.content_type = content_type


class StorageMagicBytesMismatch(StorageError):
    """Levantada quando o magic bytes não corresponde ao content-type declarado."""

    def __init__(self, declared: str, detected: Optional[str]) -> None:
        super().__init__(
            f"Magic bytes do arquivo não correspondem ao tipo declarado. "
            f"Declarado: {declared!r}, Detectado: {detected!r}. "
            f"Possível tentativa de bypass de validação."
        )
        self.declared = declared
        self.detected = detected


class StorageUploadError(StorageError):
    """Levantada quando o upload para o R2/S3 falha."""


class StorageKeyNotFound(StorageError):
    """Levantada quando a chave não existe no bucket."""


# ---------------------------------------------------------------------------
# Classe abstrata — interface do storage adapter
# ---------------------------------------------------------------------------


class StorageAdapter(ABC):
    """Interface para operações de armazenamento de arquivos.

    Segue o padrão ABC + implementação concreta já adotado no projeto.
    Permite substituição futura por outros provedores (S3, GCS, etc.)
    sem alterar a camada de aplicação.
    """

    @abstractmethod
    async def upload(
        self,
        key: str,
        data: bytes,
        content_type: str,
    ) -> str:
        """Faz upload de um arquivo para o bucket.

        Realiza validação completa antes do upload:
        1. Tamanho máximo (STORAGE_MAX_FILE_SIZE)
        2. Content-type na whitelist (ALLOWED_CONTENT_TYPES)
        3. Magic bytes vs. content-type declarado

        Args:
            key: Caminho do arquivo no bucket (ex: 'company_id/checklist/uuid.pdf').
            data: Conteúdo binário do arquivo.
            content_type: MIME type declarado (ex: 'application/pdf').

        Returns:
            A chave (key) confirmada após upload bem-sucedido.

        Raises:
            StorageSizeLimitExceeded: Se o arquivo ultrapassar 20 MB.
            StorageContentTypeNotAllowed: Se o tipo não estiver na whitelist.
            StorageMagicBytesMismatch: Se o magic bytes não bater com o content-type.
            StorageUploadError: Se o upload falhar no provedor.
        """
        ...

    @abstractmethod
    async def get_signed_url(
        self,
        key: str,
        expires_in: int,
    ) -> str:
        """Gera uma URL assinada temporária para download seguro.

        Args:
            key: Caminho do arquivo no bucket.
            expires_in: Tempo de expiração em segundos.

        Returns:
            URL assinada com tempo de vida limitado.

        Raises:
            StorageKeyNotFound: Se a chave não existir no bucket.
            StorageError: Se a geração da URL falhar.
        """
        ...

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove um arquivo do bucket (operação irreversível).

        Chamado apenas pelo worker de limpeza após soft delete no banco.

        Args:
            key: Caminho do arquivo no bucket.

        Raises:
            StorageKeyNotFound: Se a chave não existir.
            StorageError: Se a remoção falhar.
        """
        ...


# ---------------------------------------------------------------------------
# Implementação Cloudflare R2 / AWS S3 via boto3
# ---------------------------------------------------------------------------


class R2StorageAdapter(StorageAdapter):
    """Adaptador para Cloudflare R2 / S3-compatible via SDK boto3.

    Utiliza asyncio.to_thread() para não bloquear o event loop, seguindo
    o mesmo padrão já adotado no ResendAdapter (email).

    Uso exclusivo via file_router e worker de limpeza.
    NUNCA instanciar diretamente em handlers de request que não sejam de upload.
    """

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        region: Optional[str] = None,
        signed_url_expires: Optional[int] = None,
        max_file_size: Optional[int] = None,
    ) -> None:
        self._bucket = bucket_name or settings.STORAGE_BUCKET_NAME
        self._endpoint_url = endpoint_url or settings.STORAGE_ENDPOINT_URL
        self._access_key_id = access_key_id or settings.STORAGE_ACCESS_KEY_ID
        self._secret_access_key = secret_access_key or settings.STORAGE_SECRET_ACCESS_KEY
        self._region = region or settings.STORAGE_REGION
        self._signed_url_expires = signed_url_expires or settings.STORAGE_SIGNED_URL_EXPIRES
        self._max_file_size = max_file_size or settings.STORAGE_MAX_FILE_SIZE

    def _get_client(self) -> "boto3.client":
        """Cria cliente boto3 para S3/R2. Síncrono — chamado dentro de to_thread."""
        return boto3.client(
            "s3",
            endpoint_url=self._endpoint_url,
            aws_access_key_id=self._access_key_id,
            aws_secret_access_key=self._secret_access_key,
            region_name=self._region,
            config=Config(
                signature_version="s3v4",
                connect_timeout=10,
                read_timeout=30,
                retries={"max_attempts": 3, "mode": "adaptive"},
            ),
        )

    def _validate(self, data: bytes, content_type: str) -> None:
        """Valida tamanho, tipo permitido e magic bytes do arquivo.

        Args:
            data: Conteúdo binário do arquivo.
            content_type: MIME type declarado pelo cliente.

        Raises:
            StorageSizeLimitExceeded: Se exceder o limite configurado.
            StorageContentTypeNotAllowed: Se o tipo não estiver na whitelist.
            StorageMagicBytesMismatch: Se magic bytes divergirem do tipo declarado.
        """
        # 1. Validação de tamanho
        if len(data) > self._max_file_size:
            raise StorageSizeLimitExceeded(len(data), self._max_file_size)

        # 2. Normalizar e validar content-type na whitelist
        normalized_ct = content_type.split(";")[0].strip().lower()
        if normalized_ct not in ALLOWED_CONTENT_TYPES:
            raise StorageContentTypeNotAllowed(normalized_ct)

        # 3. Verificar magic bytes (mínimo 12 bytes para análise)
        if len(data) >= 12:
            detected = _detect_mime_from_magic(data[:12])
            if detected is not None:
                # Tipos equivalentes: OLE2 cobre doc, xls, ppt
                ole2_types = {
                    "application/msword",
                    "application/vnd.ms-excel",
                    "application/vnd.ms-powerpoint",
                }
                # OOXML (docx, xlsx, pptx) são ZIP internamente
                ooxml_types = {
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                }
                zip_types = {"application/zip", "application/x-zip-compressed"}

                detected_is_zip = detected == "application/zip"
                declared_is_ooxml = normalized_ct in ooxml_types
                declared_is_zip = normalized_ct in zip_types

                detected_is_ole2 = detected == "application/msword"
                declared_is_ole2 = normalized_ct in ole2_types

                # ZIP também inclui OOXML — ambos são válidos se magic bater
                if detected_is_zip and (declared_is_ooxml or declared_is_zip):
                    return
                if detected_is_ole2 and declared_is_ole2:
                    return
                if detected != normalized_ct:
                    raise StorageMagicBytesMismatch(normalized_ct, detected)

    def _sync_upload(self, key: str, data: bytes, content_type: str) -> None:
        """Upload síncrono — executado via to_thread."""
        client = self._get_client()
        try:
            client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
            )
            logger.info(
                "Upload bem-sucedido: bucket=%s key=%s size=%d bytes content_type=%s",
                self._bucket,
                key,
                len(data),
                content_type,
            )
        except (ClientError, BotoCoreError) as exc:
            raise StorageUploadError(
                f"Falha no upload para R2/S3: bucket={self._bucket!r} key={key!r}: {exc}"
            ) from exc

    def _sync_get_signed_url(self, key: str, expires_in: int) -> str:
        """Geração de signed URL síncrona — executado via to_thread."""
        client = self._get_client()
        try:
            url: str = client.generate_presigned_url(
                ClientMethod="get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_in,
            )
            logger.debug("Signed URL gerada: key=%s expires_in=%ds", key, expires_in)
            return url
        except (ClientError, BotoCoreError) as exc:
            raise StorageError(
                f"Falha ao gerar signed URL: bucket={self._bucket!r} key={key!r}: {exc}"
            ) from exc

    def _sync_delete(self, key: str) -> None:
        """Remoção síncrona — executado via to_thread."""
        client = self._get_client()
        try:
            # Verificar existência antes de remover
            client.head_object(Bucket=self._bucket, Key=key)
            client.delete_object(Bucket=self._bucket, Key=key)
            logger.info("Arquivo removido do bucket: key=%s", key)
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code in {"404", "NoSuchKey"}:
                raise StorageKeyNotFound(
                    f"Arquivo não encontrado no bucket: key={key!r}"
                ) from exc
            raise StorageError(
                f"Falha ao remover arquivo: bucket={self._bucket!r} key={key!r}: {exc}"
            ) from exc
        except BotoCoreError as exc:
            raise StorageError(
                f"Erro de conexão ao remover arquivo: key={key!r}: {exc}"
            ) from exc

    async def upload(
        self,
        key: str,
        data: bytes,
        content_type: str,
    ) -> str:
        """Valida e faz upload assíncrono para R2/S3."""
        self._validate(data, content_type)
        await asyncio.to_thread(self._sync_upload, key, data, content_type)
        return key

    async def get_signed_url(self, key: str, expires_in: int) -> str:
        """Gera signed URL assíncrona para download seguro."""
        return await asyncio.to_thread(self._sync_get_signed_url, key, expires_in)

    async def delete(self, key: str) -> None:
        """Remove arquivo do bucket de forma assíncrona."""
        await asyncio.to_thread(self._sync_delete, key)


# ---------------------------------------------------------------------------
# Factory function para injeção de dependência
# ---------------------------------------------------------------------------


def get_storage_adapter() -> StorageAdapter:
    """Factory para o adaptador de storage configurado via settings.

    Usado como dependência FastAPI em file_router.
    Permite substituição em testes via override de dependência.
    """
    return R2StorageAdapter()


def build_storage_key(company_id: str, contexto: str, file_id: str, filename: str) -> str:
    """Constrói a chave (path) do arquivo no bucket de forma padronizada.

    Formato: {company_id}/{contexto}/{file_id}/{filename_sanitizado}
    Garante isolamento por empresa e contexto no bucket.

    Args:
        company_id: UUID da empresa (sem hífens).
        contexto: Contexto do arquivo (ex: 'checklist_evidencia', 'plano_acao').
        file_id: UUID único do FileAsset.
        filename: Nome original do arquivo (será sanitizado).

    Returns:
        Chave padronizada para uso como storage_key no FileAsset.
    """
    # Extrair apenas o basename para prevenir path traversal (ex: ../../etc/passwd)
    safe_filename = os.path.basename(filename)
    # Sanitizar: permitir apenas caracteres alfanuméricos, ponto e hífen/underscore
    safe_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    safe_filename = "".join(c if c in safe_chars else "_" for c in safe_filename)
    # Remover pontos iniciais para evitar arquivos ocultos/relativos
    safe_filename = safe_filename.lstrip(".")

    # Embutir file_id no último componente para evitar subdirectório extra.
    # Formato: {company_clean}/{contexto}/{file_id_clean}_{safe_filename}
    # O componente final é truncado a 200 chars para limitar o comprimento total.
    company_clean = str(company_id).replace("-", "")
    file_id_clean = str(file_id).replace("-", "")
    last_component = f"{file_id_clean}_{safe_filename}"[:200]
    return f"{company_clean}/{contexto}/{last_component}"
