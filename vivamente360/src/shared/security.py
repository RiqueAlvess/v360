import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

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
