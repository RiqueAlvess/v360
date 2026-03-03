from enum import Enum


class UserRole(str, Enum):
    """Papéis de acesso disponíveis para usuários no sistema."""

    ADMIN = "admin"
    MANAGER = "manager"
    RESPONDENT = "respondent"
