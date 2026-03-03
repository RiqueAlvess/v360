"""Testes unitários para exceções de domínio."""

import pytest
from uuid import uuid4

from src.shared.exceptions import (
    BaseAppException,
    ConflictError,
    DomainException,
    ForbiddenError,
    InfrastructureException,
    NotFoundError,
    RateLimitError,
    UnauthorizedError,
    ValidationError,
)


class TestNotFoundError:
    def test_message_sem_id(self) -> None:
        exc = NotFoundError(resource="Usuário")
        assert exc.message == "Usuário não encontrado(a)."
        assert exc.code == "NOT_FOUND"
        assert exc.details["resource"] == "Usuário"

    def test_message_com_id(self) -> None:
        resource_id = uuid4()
        exc = NotFoundError(resource="Campanha", resource_id=resource_id)
        assert str(resource_id) in exc.details["resource_id"]

    def test_to_dict(self) -> None:
        exc = NotFoundError(resource="Empresa")
        result = exc.to_dict()
        assert result["error"] == "NOT_FOUND"
        assert "message" in result
        assert "details" in result


class TestValidationError:
    def test_com_field(self) -> None:
        exc = ValidationError(message="Email inválido", field="email")
        assert exc.details["field"] == "email"
        assert exc.code == "VALIDATION_ERROR"

    def test_sem_field(self) -> None:
        exc = ValidationError(message="Dados inválidos")
        assert "field" not in exc.details


class TestUnauthorizedError:
    def test_mensagem_padrao(self) -> None:
        exc = UnauthorizedError()
        assert exc.code == "UNAUTHORIZED"
        assert "Autenticação" in exc.message

    def test_mensagem_customizada(self) -> None:
        exc = UnauthorizedError(message="Token expirado.")
        assert "Token expirado" in exc.message


class TestForbiddenError:
    def test_padrao(self) -> None:
        exc = ForbiddenError()
        assert exc.code == "FORBIDDEN"


class TestRateLimitError:
    def test_com_retry_after(self) -> None:
        exc = RateLimitError(retry_after_seconds=60)
        assert exc.details["retry_after_seconds"] == 60
        assert exc.code == "RATE_LIMIT_EXCEEDED"


class TestInfrastructureException:
    def test_com_service(self) -> None:
        exc = InfrastructureException(service="email")
        assert exc.details["service"] == "email"
        assert exc.code == "SERVICE_UNAVAILABLE"


class TestHierarquia:
    def test_not_found_e_domain(self) -> None:
        exc = NotFoundError(resource="X")
        assert isinstance(exc, DomainException)
        assert isinstance(exc, BaseAppException)

    def test_conflict_e_domain(self) -> None:
        exc = ConflictError(message="Conflito")
        assert isinstance(exc, DomainException)

    def test_unauthorized_nao_e_domain(self) -> None:
        exc = UnauthorizedError()
        assert not isinstance(exc, DomainException)
        assert isinstance(exc, BaseAppException)
