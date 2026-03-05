"""Testes unitários do módulo shared/exceptions.py.

Cobre todas as exceções customizadas com mensagens parametrizadas:
    - DomainException: base, detail customizado, contexto extra
    - NotFoundError: com e sem resource_id
    - UnauthorizedError: mensagem padrão e customizada
    - ForbiddenError: mensagem padrão e customizada
    - ValidationError: com e sem campo
    - ConflictError: mensagem customizada
    - RateLimitError: mensagem customizada
"""
import pytest

from src.shared.exceptions import (
    ConflictError,
    DomainException,
    ForbiddenError,
    NotFoundError,
    RateLimitError,
    UnauthorizedError,
    ValidationError,
)


# ---------------------------------------------------------------------------
# DomainException (base)
# ---------------------------------------------------------------------------


class TestDomainException:
    """Testa a classe base de exceções de domínio."""

    def test_default_detail_when_no_message_provided(self) -> None:
        """Sem detail, usa o class-level default."""
        exc = DomainException()
        assert exc.detail == "An unexpected domain error occurred."

    def test_custom_detail_overrides_default(self) -> None:
        """detail passado no construtor deve sobrescrever o default da classe."""
        exc = DomainException(detail="Algo deu errado.")
        assert exc.detail == "Algo deu errado."

    def test_extra_context_stored(self) -> None:
        """Kwargs extras devem ser armazenados em .context."""
        exc = DomainException(detail="Erro", user_id="123", action="delete")
        assert exc.context["user_id"] == "123"
        assert exc.context["action"] == "delete"

    def test_is_subclass_of_exception(self) -> None:
        """DomainException deve herdar de Exception."""
        assert issubclass(DomainException, Exception)

    def test_str_representation(self) -> None:
        """str() deve retornar o detail."""
        exc = DomainException(detail="Mensagem de erro")
        assert str(exc) == "Mensagem de erro"

    def test_repr_contains_class_name_and_detail(self) -> None:
        """repr() deve incluir o nome da classe e o detail."""
        exc = DomainException(detail="Repr test")
        r = repr(exc)
        assert "DomainException" in r
        assert "Repr test" in r

    def test_default_status_code_is_500(self) -> None:
        """Status code padrão deve ser 500."""
        assert DomainException.status_code == 500


# ---------------------------------------------------------------------------
# NotFoundError
# ---------------------------------------------------------------------------


class TestNotFoundError:
    """Testa exceção para recursos não encontrados (HTTP 404)."""

    def test_status_code_is_404(self) -> None:
        """NotFoundError deve ter status_code 404."""
        assert NotFoundError.status_code == 404

    def test_default_message_without_id(self) -> None:
        """Sem resource_id, mensagem menciona apenas o resource."""
        exc = NotFoundError(resource="Campaign")
        assert "Campaign" in exc.detail
        assert "not found" in exc.detail.lower()

    def test_message_with_resource_id(self) -> None:
        """Com resource_id, mensagem inclui o ID para facilitar debug."""
        exc = NotFoundError(resource="User", resource_id="abc-123")
        assert "User" in exc.detail
        assert "abc-123" in exc.detail

    def test_default_resource_is_resource(self) -> None:
        """Sem argumentos, usa 'Resource' como nome padrão."""
        exc = NotFoundError()
        assert "Resource" in exc.detail

    def test_context_stores_resource_and_id(self) -> None:
        """Context deve armazenar resource e resource_id para logging."""
        exc = NotFoundError(resource="Campaign", resource_id="uuid-999")
        assert exc.context["resource"] == "Campaign"
        assert exc.context["resource_id"] == "uuid-999"

    def test_is_raiseable(self) -> None:
        """Deve ser possível levantar e capturar a exceção normalmente."""
        with pytest.raises(NotFoundError) as exc_info:
            raise NotFoundError(resource="Survey", resource_id=42)
        assert "Survey" in exc_info.value.detail

    def test_is_subclass_of_domain_exception(self) -> None:
        """NotFoundError deve herdar de DomainException."""
        assert issubclass(NotFoundError, DomainException)


# ---------------------------------------------------------------------------
# UnauthorizedError
# ---------------------------------------------------------------------------


class TestUnauthorizedError:
    """Testa exceção de autenticação (HTTP 401)."""

    def test_status_code_is_401(self) -> None:
        assert UnauthorizedError.status_code == 401

    def test_default_message(self) -> None:
        exc = UnauthorizedError()
        assert exc.detail == "Authentication required."

    def test_custom_message(self) -> None:
        exc = UnauthorizedError(detail="Token expirado.")
        assert exc.detail == "Token expirado."

    def test_is_raiseable_and_catchable(self) -> None:
        with pytest.raises(UnauthorizedError, match="Token expirado"):
            raise UnauthorizedError(detail="Token expirado.")

    def test_is_subclass_of_domain_exception(self) -> None:
        assert issubclass(UnauthorizedError, DomainException)


# ---------------------------------------------------------------------------
# ForbiddenError
# ---------------------------------------------------------------------------


class TestForbiddenError:
    """Testa exceção de autorização (HTTP 403)."""

    def test_status_code_is_403(self) -> None:
        assert ForbiddenError.status_code == 403

    def test_default_message(self) -> None:
        exc = ForbiddenError()
        assert "permission" in exc.detail.lower()

    def test_custom_message(self) -> None:
        exc = ForbiddenError(detail="Apenas administradores podem acessar este recurso.")
        assert "administradores" in exc.detail

    def test_is_raiseable(self) -> None:
        with pytest.raises(ForbiddenError):
            raise ForbiddenError()

    def test_is_subclass_of_domain_exception(self) -> None:
        assert issubclass(ForbiddenError, DomainException)


# ---------------------------------------------------------------------------
# ValidationError
# ---------------------------------------------------------------------------


class TestValidationError:
    """Testa exceção de validação de regra de negócio (HTTP 422)."""

    def test_status_code_is_422(self) -> None:
        assert ValidationError.status_code == 422

    def test_default_message(self) -> None:
        exc = ValidationError()
        assert exc.detail == "Validation failed."

    def test_custom_message(self) -> None:
        exc = ValidationError(detail="O campo email é inválido.")
        assert exc.detail == "O campo email é inválido."

    def test_field_stored_in_context(self) -> None:
        """Campo inválido deve ser armazenado no context para feedback ao cliente."""
        exc = ValidationError(detail="Campo inválido.", field="email")
        assert exc.context.get("field") == "email"

    def test_without_field(self) -> None:
        """Sem field, context deve ter None ou ausência da chave."""
        exc = ValidationError(detail="Erro de validação.")
        assert exc.context.get("field") is None

    def test_is_raiseable(self) -> None:
        with pytest.raises(ValidationError, match="inválido"):
            raise ValidationError(detail="Campo inválido.", field="cpf")

    def test_is_subclass_of_domain_exception(self) -> None:
        assert issubclass(ValidationError, DomainException)


# ---------------------------------------------------------------------------
# ConflictError
# ---------------------------------------------------------------------------


class TestConflictError:
    """Testa exceção de conflito de estado (HTTP 409)."""

    def test_status_code_is_409(self) -> None:
        assert ConflictError.status_code == 409

    def test_default_message(self) -> None:
        exc = ConflictError()
        assert "conflict" in exc.detail.lower()

    def test_custom_message(self) -> None:
        exc = ConflictError(detail="Email já cadastrado.")
        assert exc.detail == "Email já cadastrado."

    def test_is_raiseable(self) -> None:
        with pytest.raises(ConflictError, match="já cadastrado"):
            raise ConflictError(detail="Email já cadastrado.")

    def test_is_subclass_of_domain_exception(self) -> None:
        assert issubclass(ConflictError, DomainException)


# ---------------------------------------------------------------------------
# RateLimitError
# ---------------------------------------------------------------------------


class TestRateLimitError:
    """Testa exceção de rate limit (HTTP 429)."""

    def test_status_code_is_429(self) -> None:
        assert RateLimitError.status_code == 429

    def test_default_message(self) -> None:
        exc = RateLimitError()
        assert "rate limit" in exc.detail.lower() or "limit" in exc.detail.lower()

    def test_custom_message(self) -> None:
        exc = RateLimitError(detail="Máximo de 10 análises IA por hora atingido.")
        assert "10" in exc.detail

    def test_is_raiseable(self) -> None:
        with pytest.raises(RateLimitError):
            raise RateLimitError()

    def test_is_subclass_of_domain_exception(self) -> None:
        assert issubclass(RateLimitError, DomainException)


# ---------------------------------------------------------------------------
# Hierarquia de herança
# ---------------------------------------------------------------------------


class TestExceptionHierarchy:
    """Garante que todas as exceções herdam de DomainException (polimorfismo)."""

    @pytest.mark.parametrize(
        "exc_class",
        [
            NotFoundError,
            UnauthorizedError,
            ForbiddenError,
            ValidationError,
            ConflictError,
            RateLimitError,
        ],
    )
    def test_all_exceptions_are_domain_exceptions(self, exc_class: type) -> None:
        """Todas as exceções customizadas devem ser capturáveis como DomainException."""
        assert issubclass(exc_class, DomainException)
        # Verificar que instâncias são capturáveis pelo tipo base
        exc = exc_class()
        assert isinstance(exc, DomainException)

    @pytest.mark.parametrize(
        "exc_class",
        [
            NotFoundError,
            UnauthorizedError,
            ForbiddenError,
            ValidationError,
            ConflictError,
            RateLimitError,
        ],
    )
    def test_all_exceptions_are_python_exceptions(self, exc_class: type) -> None:
        """Todas devem ser capturáveis como Exception nativa do Python."""
        assert issubclass(exc_class, Exception)
