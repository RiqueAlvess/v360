import base64
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from jose import JWTError, jwt

from src.shared.config import settings

JWT_ALGORITHM: str = "HS256"


def create_access_token(
    subject: str,
    company_id: str,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Gera um JWT de curta duração com claims de usuário e empresa.

    O token não é persistido — expira naturalmente pelo TTL configurado.
    """
    expire = datetime.now(tz=timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {
        "sub": subject,
        "company_id": company_id,
        "role": role,
        "exp": expire,
        "iat": datetime.now(tz=timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decodifica e valida um JWT. Levanta ValueError se inválido ou expirado."""
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
        )
        return payload
    except JWTError as exc:
        raise ValueError("Token inválido ou expirado") from exc


def hash_token(value: str) -> str:
    """SHA-256 hex digest — armazena tokens no banco sem expor o valor raw."""
    return hashlib.sha256(value.encode()).hexdigest()


def generate_refresh_token() -> str:
    """Gera token aleatório criptograficamente seguro (URL-safe, 43 chars)."""
    return secrets.token_urlsafe(32)


def _derive_aes_key(key_str: str) -> bytes:
    """Deriva chave AES-256 (32 bytes) via SHA-256 da chave de configuração."""
    return hashlib.sha256(key_str.encode("utf-8")).digest()


def encrypt_data(plaintext: str, key: str) -> str:
    """Cifra texto com AES-256-GCM.

    Retorna base64(nonce‖ciphertext‖tag) — seguro para armazenar em JSONB.
    O nonce de 12 bytes é gerado aleatoriamente para cada ciframento.

    Args:
        plaintext: Texto a ser cifrado.
        key: Chave de configuração (mínimo 32 chars); derivada via SHA-256.

    Returns:
        String base64 contendo nonce + ciphertext + tag.
    """
    aes_key = _derive_aes_key(key)
    aesgcm = AESGCM(aes_key)
    nonce = os.urandom(12)  # 96-bit nonce recomendado para GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_data(encrypted: str, key: str) -> str:
    """Decifra texto cifrado com AES-256-GCM (inverso de encrypt_data).

    Args:
        encrypted: String base64 gerada por encrypt_data.
        key: Mesma chave usada na cifragem.

    Returns:
        Texto original em plaintext.

    Raises:
        ValueError: Se os dados estiverem corrompidos ou a chave for inválida.
    """
    try:
        aes_key = _derive_aes_key(key)
        aesgcm = AESGCM(aes_key)
        raw = base64.b64decode(encrypted)
        nonce, ciphertext = raw[:12], raw[12:]
        return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")
    except Exception as exc:
        raise ValueError("Falha ao decifrar dados — chave inválida ou dados corrompidos") from exc
