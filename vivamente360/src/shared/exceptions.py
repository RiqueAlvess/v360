"""Exceções de domínio tipadas para VIVAMENTE 360º.

Hierarquia:
    BaseAppException
    ├── DomainException          — violações de regras de negócio
    │   ├── NotFoundError        — recurso não encontrado
    │   ├── ConflictError        — conflito de estado (ex: email duplicado)
    │   └── ValidationError      — dados inválidos para o domínio
    ├── UnauthorizedError        — não autenticado (401)
    ├── ForbiddenError           — autenticado mas sem permissão (403)
    ├── RateLimitError           — limite de requisições atingido (429)
    └── InfrastructureException  — falhas de infra (DB, email, queue)
"""

from typing import Any, Optional
from uuid import UUID


class BaseAppException(Exception):
    """Exceção base para toda a aplicação.

    Todos os erros customizados devem herdar desta classe para garantir
    tratamento centralizado no middleware de exceções do FastAPI.
    """

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        self.message = message
        self.code = code
        self.details: dict[str, Any] = details or {}
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        """Serializa a exceção para resposta HTTP."""
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


# ── Exceções de Domínio ────────────────────────────────────────────────────


class DomainException(BaseAppException):
    """Exceção base para violações de regras de negócio.

    Use subclasses específicas para contextos concretos.
    """

    def __init__(
        self,
        message: str,
        code: str = "DOMAIN_ERROR",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(message=message, code=code, details=details)


class NotFoundError(DomainException):
    """Recurso solicitado não foi encontrado.

    Mapeia para HTTP 404. Use quando uma entidade não existe no banco,
    ou foi excluída, e o caller espera que exista.
    """

    def __init__(
        self,
        resource: str,
        resource_id: Optional[UUID | str | int] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        _details = details or {}
        if resource_id is not None:
            _details["resource_id"] = str(resource_id)
        _details["resource"] = resource

        super().__init__(
            message=f"{resource} não encontrado(a).",
            code="NOT_FOUND",
            details=_details,
        )


class ConflictError(DomainException):
    """Conflito de estado — o recurso já existe ou está em estado inválido.

    Mapeia para HTTP 409. Use para email duplicado, CPF já cadastrado, etc.
    """

    def __init__(
        self,
        message: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            code="CONFLICT",
            details=details,
        )


class ValidationError(DomainException):
    """Dados inválidos para as regras de negócio do domínio.

    Mapeia para HTTP 422. Diferente do ValidationError do Pydantic —
    este é para regras de negócio, não de formato/tipo.
    """

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        _details = details or {}
        if field:
            _details["field"] = field

        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details=_details,
        )


# ── Exceções de Segurança ──────────────────────────────────────────────────


class UnauthorizedError(BaseAppException):
    """Usuário não autenticado ou credenciais inválidas.

    Mapeia para HTTP 401. Use quando:
    - Token ausente ou inválido
    - Credenciais incorretas no login
    - Token expirado e não renovado
    """

    def __init__(
        self,
        message: str = "Autenticação necessária.",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            code="UNAUTHORIZED",
            details=details,
        )


class ForbiddenError(BaseAppException):
    """Usuário autenticado mas sem permissão para o recurso.

    Mapeia para HTTP 403. Use quando:
    - Usuário tenta acessar dados de outra empresa
    - Papel insuficiente para a operação
    - Ação bloqueada por RLS
    """

    def __init__(
        self,
        message: str = "Acesso negado.",
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            code="FORBIDDEN",
            details=details,
        )


class RateLimitError(BaseAppException):
    """Limite de requisições atingido.

    Mapeia para HTTP 429.
    """

    def __init__(
        self,
        message: str = "Muitas requisições. Aguarde antes de tentar novamente.",
        retry_after_seconds: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        _details = details or {}
        if retry_after_seconds is not None:
            _details["retry_after_seconds"] = retry_after_seconds

        super().__init__(
            message=message,
            code="RATE_LIMIT_EXCEEDED",
            details=_details,
        )


# ── Exceções de Infraestrutura ─────────────────────────────────────────────


class InfrastructureException(BaseAppException):
    """Falha em serviço de infraestrutura (banco, email, fila).

    Mapeia para HTTP 503. Não deve vazar detalhes internos para o cliente.
    """

    def __init__(
        self,
        message: str = "Serviço temporariamente indisponível.",
        service: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        _details = details or {}
        if service:
            _details["service"] = service

        super().__init__(
            message=message,
            code="SERVICE_UNAVAILABLE",
            details=_details,
        )
