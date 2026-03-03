import uuid
from dataclasses import dataclass, field
from typing import Optional

from passlib.context import CryptContext

from src.domain.enums.user_role import UserRole

_pwd_context: CryptContext = CryptContext(schemes=["bcrypt"], deprecated="auto")


@dataclass
class User:
    """Entidade de domínio do usuário.

    Representa o conceito de negócio independente do modelo ORM.
    O email nunca é armazenado em texto puro — apenas hash e versão cifrada.
    """

    id: uuid.UUID
    company_id: uuid.UUID
    email_hash: str
    email_criptografado: bytes
    hashed_password: str
    role: UserRole
    ativo: bool
    nome: Optional[str] = field(default=None)

    def verify_password(self, plain_password: str) -> bool:
        """Verifica a senha em texto puro contra o hash bcrypt armazenado."""
        return _pwd_context.verify(plain_password, self.hashed_password)

    @property
    def is_active(self) -> bool:
        """Indica se o usuário está ativo na plataforma."""
        return self.ativo

    @property
    def full_name(self) -> str:
        """Nome completo do usuário; fallback para identificador parcial se ausente."""
        return self.nome or f"Usuário {str(self.id)[:8]}"
