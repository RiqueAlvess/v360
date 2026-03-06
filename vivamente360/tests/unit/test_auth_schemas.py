"""Testes unitários dos schemas Pydantic de autenticação (auth_schemas.py).

Valida todos os modelos de request e response:
    - LoginRequest: email válido, email inválido, senha vazia, strip whitespace
    - RefreshRequest: refresh_token obrigatório e não vazio
    - LogoutRequest: refresh_token obrigatório e não vazio
    - TokenResponse: campos obrigatórios, token_type default
"""
import pytest
from pydantic import ValidationError

from src.presentation.schemas.auth_schemas import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
)


# ---------------------------------------------------------------------------
# LoginRequest
# ---------------------------------------------------------------------------


class TestLoginRequest:
    def test_login_request_valid(self) -> None:
        """LoginRequest aceita email e senha válidos."""
        req = LoginRequest(email="user@example.com", password="senha123")

        assert req.email == "user@example.com"
        assert req.password == "senha123"

    def test_login_request_invalid_email_raises_validation_error(self) -> None:
        """LoginRequest rejeita email sem formato válido."""
        with pytest.raises(ValidationError) as exc_info:
            LoginRequest(email="nao_e_email", password="senha123")

        errors = exc_info.value.errors()
        field_names = [e["loc"][0] for e in errors]
        assert "email" in field_names

    def test_login_request_missing_email_raises_validation_error(self) -> None:
        """LoginRequest rejeita payload sem campo email."""
        with pytest.raises(ValidationError) as exc_info:
            LoginRequest(password="senha123")  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        field_names = [e["loc"][0] for e in errors]
        assert "email" in field_names

    def test_login_request_empty_password_raises_validation_error(self) -> None:
        """LoginRequest rejeita senha vazia (min_length=1)."""
        with pytest.raises(ValidationError) as exc_info:
            LoginRequest(email="user@example.com", password="")

        errors = exc_info.value.errors()
        field_names = [e["loc"][0] for e in errors]
        assert "password" in field_names

    def test_login_request_missing_password_raises_validation_error(self) -> None:
        """LoginRequest rejeita payload sem campo password."""
        with pytest.raises(ValidationError) as exc_info:
            LoginRequest(email="user@example.com")  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        field_names = [e["loc"][0] for e in errors]
        assert "password" in field_names

    def test_login_request_strips_email_whitespace(self) -> None:
        """LoginRequest aplica str_strip_whitespace ao email."""
        req = LoginRequest(email="  user@example.com  ", password="senha123")

        assert req.email == "user@example.com"

    def test_login_request_strips_password_whitespace(self) -> None:
        """LoginRequest aplica str_strip_whitespace à senha."""
        req = LoginRequest(email="user@example.com", password="  senha123  ")

        assert req.password == "senha123"

    def test_login_request_email_with_plus_sign(self) -> None:
        """LoginRequest aceita email com sinal de + (formato válido)."""
        req = LoginRequest(email="user+tag@example.com", password="senha")

        assert "+" in req.email

    def test_login_request_both_fields_missing_raises_validation_error(self) -> None:
        """LoginRequest rejeita payload completamente vazio."""
        with pytest.raises(ValidationError) as exc_info:
            LoginRequest()  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        assert len(errors) >= 2


# ---------------------------------------------------------------------------
# RefreshRequest
# ---------------------------------------------------------------------------


class TestRefreshRequest:
    def test_refresh_request_valid(self) -> None:
        """RefreshRequest aceita refresh_token não vazio."""
        req = RefreshRequest(refresh_token="algum_token_valido")

        assert req.refresh_token == "algum_token_valido"

    def test_refresh_request_empty_token_raises_validation_error(self) -> None:
        """RefreshRequest rejeita refresh_token vazio (min_length=1)."""
        with pytest.raises(ValidationError) as exc_info:
            RefreshRequest(refresh_token="")

        errors = exc_info.value.errors()
        field_names = [e["loc"][0] for e in errors]
        assert "refresh_token" in field_names

    def test_refresh_request_missing_token_raises_validation_error(self) -> None:
        """RefreshRequest rejeita payload sem campo refresh_token."""
        with pytest.raises(ValidationError) as exc_info:
            RefreshRequest()  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        field_names = [e["loc"][0] for e in errors]
        assert "refresh_token" in field_names

    def test_refresh_request_strips_whitespace(self) -> None:
        """RefreshRequest aplica str_strip_whitespace ao token."""
        req = RefreshRequest(refresh_token="  token_com_espacos  ")

        assert req.refresh_token == "token_com_espacos"


# ---------------------------------------------------------------------------
# LogoutRequest
# ---------------------------------------------------------------------------


class TestLogoutRequest:
    def test_logout_request_valid(self) -> None:
        """LogoutRequest aceita refresh_token não vazio."""
        req = LogoutRequest(refresh_token="token_valido_para_revogar")

        assert req.refresh_token == "token_valido_para_revogar"

    def test_logout_request_empty_token_raises_validation_error(self) -> None:
        """LogoutRequest rejeita refresh_token vazio (min_length=1)."""
        with pytest.raises(ValidationError) as exc_info:
            LogoutRequest(refresh_token="")

        errors = exc_info.value.errors()
        field_names = [e["loc"][0] for e in errors]
        assert "refresh_token" in field_names

    def test_logout_request_missing_token_raises_validation_error(self) -> None:
        """LogoutRequest rejeita payload sem campo refresh_token."""
        with pytest.raises(ValidationError) as exc_info:
            LogoutRequest()  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        field_names = [e["loc"][0] for e in errors]
        assert "refresh_token" in field_names

    def test_logout_request_strips_whitespace(self) -> None:
        """LogoutRequest aplica str_strip_whitespace ao token."""
        req = LogoutRequest(refresh_token="  token_logout  ")

        assert req.refresh_token == "token_logout"


# ---------------------------------------------------------------------------
# TokenResponse
# ---------------------------------------------------------------------------


class TestTokenResponse:
    def test_token_response_valid(self) -> None:
        """TokenResponse aceita access_token e refresh_token."""
        resp = TokenResponse(
            access_token="jwt.access.token",
            refresh_token="raw_refresh_token",
        )

        assert resp.access_token == "jwt.access.token"
        assert resp.refresh_token == "raw_refresh_token"
        assert resp.token_type == "bearer"

    def test_token_response_default_token_type(self) -> None:
        """TokenResponse usa 'bearer' como token_type padrão."""
        resp = TokenResponse(
            access_token="jwt.access.token",
            refresh_token="raw_refresh_token",
        )

        assert resp.token_type == "bearer"

    def test_token_response_missing_access_token_raises_validation_error(self) -> None:
        """TokenResponse rejeita payload sem access_token."""
        with pytest.raises(ValidationError) as exc_info:
            TokenResponse(refresh_token="raw_refresh_token")  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        field_names = [e["loc"][0] for e in errors]
        assert "access_token" in field_names

    def test_token_response_missing_refresh_token_raises_validation_error(self) -> None:
        """TokenResponse rejeita payload sem refresh_token."""
        with pytest.raises(ValidationError) as exc_info:
            TokenResponse(access_token="jwt.access.token")  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        field_names = [e["loc"][0] for e in errors]
        assert "refresh_token" in field_names

    def test_token_response_both_required_fields_missing_raises_validation_error(self) -> None:
        """TokenResponse rejeita payload sem access_token nem refresh_token."""
        with pytest.raises(ValidationError) as exc_info:
            TokenResponse()  # type: ignore[call-arg]

        errors = exc_info.value.errors()
        assert len(errors) >= 2

    def test_token_response_custom_token_type(self) -> None:
        """TokenResponse aceita token_type personalizado."""
        resp = TokenResponse(
            access_token="jwt.token",
            refresh_token="raw_token",
            token_type="Bearer",
        )

        assert resp.token_type == "Bearer"
