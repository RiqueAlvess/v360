import asyncio
from typing import Any

import boto3
from botocore.client import BaseClient


class R2Adapter:
    """Adaptador S3-compatible para Cloudflare R2.

    Todas as chamadas ao SDK boto3 (síncrono) são executadas em thread pool
    via asyncio.to_thread() para não bloquear o event loop do FastAPI.
    """

    def __init__(
        self,
        account_id: str,
        access_key: str,
        secret_key: str,
        bucket_name: str,
    ) -> None:
        self._bucket = bucket_name
        self._client: BaseClient = boto3.client(
            "s3",
            endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

    async def upload(self, key: str, data: bytes, mime_type: str) -> str:
        """Faz upload de objeto para o bucket R2 e retorna o r2_key."""

        def _put() -> None:
            self._client.put_object(
                Bucket=self._bucket,
                Key=key,
                Body=data,
                ContentType=mime_type,
            )

        await asyncio.to_thread(_put)
        return key

    async def signed_url(self, key: str, expires_in: int = 3600) -> str:
        """Gera URL pré-assinada temporária (GET) com validade em segundos."""

        def _presign() -> Any:
            return self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_in,
            )

        return await asyncio.to_thread(_presign)  # type: ignore[return-value]

    async def delete(self, key: str) -> None:
        """Remove objeto do bucket R2."""

        def _delete() -> None:
            self._client.delete_object(Bucket=self._bucket, Key=key)

        await asyncio.to_thread(_delete)
