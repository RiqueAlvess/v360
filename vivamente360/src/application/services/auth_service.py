from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from src.domain.entities.user import User
from src.infrastructure.repositories.token_repository import TokenRepository
from src.infrastructure.repositories.user_repository import UserRepository
from src.shared.config import settings
from src.shared.exceptions import UnauthorizedError
from src.shared.security import create_access_token, generate_refresh_token, hash_token


class AuthService:
    """Gerencia o ciclo de vida da autenticação — login, refresh e logout.

    Orquestra UserRepository e TokenRepository seguindo rotação obrigatória de tokens.
    Nunca persiste o access token; apenas o refresh token é armazenado (como hash SHA-256).
    """

    def __init__(
        self,
        user_repo: UserRepository,
        token_repo: TokenRepository,
    ) -> None:
        self._user_repo = user_repo
        self._token_repo = token_repo

    async def login(self, email: str, password: str) -> dict[str, str]:
        """Autentica o usuário com email e senha; retorna par de tokens.

        O email é normalizado (lowercase + strip) e hasheado antes da consulta,
        garantindo que o plaintext nunca seja armazenado ou logado.
        """
        email_hash: str = hash_token(email.lower().strip())
        user: Optional[User] = await self._user_repo.get_by_email_hash(email_hash)
        if not user or not user.verify_password(password):
            raise UnauthorizedError("Credenciais inválidas")
        if not user.is_active:
            raise UnauthorizedError("Conta desativada. Contate o administrador.")
        return await self._create_token_pair(user)

    async def refresh(self, refresh_token: str) -> dict[str, str]:
        """Rotaciona o refresh token — invalida o atual e emite novo par.

        Rotação obrigatória: um token usado para refresh é imediatamente revogado.
        Uso de token já revogado retorna 401 sem revelar o motivo.
        """
        token_hash: str = hash_token(refresh_token)
        stored = await self._token_repo.get_valid_token(token_hash)
        if not stored:
            raise UnauthorizedError("Token inválido ou expirado")
        await self._token_repo.revoke(stored.id)
        user: Optional[User] = await self._user_repo.get_by_id(stored.user_id)
        if not user or not user.is_active:
            raise UnauthorizedError("Usuário não encontrado ou inativo")
        return await self._create_token_pair(user)

    async def logout(self, refresh_token: str) -> None:
        """Revoga o refresh token — access token expira naturalmente pelo TTL.

        Logout silencioso: não levanta erro se o token já estiver expirado ou inválido.
        """
        token_hash: str = hash_token(refresh_token)
        stored = await self._token_repo.get_valid_token(token_hash)
        if stored:
            await self._token_repo.revoke(stored.id)

    async def _create_token_pair(self, user: User) -> dict[str, str]:
        """Gera access token (JWT, 15 min) e refresh token (UUID persistido, 30 dias)."""
        access_token: str = create_access_token(
            subject=str(user.id),
            company_id=str(user.company_id),
            role=user.role.value,
        )
        raw_refresh: str = generate_refresh_token()
        token_hash: str = hash_token(raw_refresh)
        expires_at: datetime = datetime.now(tz=timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        await self._token_repo.create(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        return {
            "access_token": access_token,
            "refresh_token": raw_refresh,
            "token_type": "bearer",
        }
