from pydantic import BaseModel, EmailStr, Field, ConfigDict


class LoginRequest(BaseModel):
    """Credenciais de login do usuário."""

    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr = Field(description="Email cadastrado na plataforma")
    password: str = Field(min_length=1, description="Senha do usuário")


class RefreshRequest(BaseModel):
    """Payload para rotação de refresh token."""

    model_config = ConfigDict(str_strip_whitespace=True)

    refresh_token: str = Field(min_length=1, description="Refresh token ativo")


class LogoutRequest(BaseModel):
    """Payload para encerramento de sessão."""

    model_config = ConfigDict(str_strip_whitespace=True)

    refresh_token: str = Field(min_length=1, description="Refresh token a revogar")


class TokenResponse(BaseModel):
    """Par de tokens retornado após login ou refresh bem-sucedido."""

    model_config = ConfigDict(str_strip_whitespace=True)

    access_token: str = Field(description="JWT de acesso (TTL: 15 min)")
    refresh_token: str = Field(description="Token de renovação (TTL: 30 dias)")
    token_type: str = Field(default="bearer", description="Tipo do token OAuth2")


class UserProfileResponse(BaseModel):
    """Perfil do usuário autenticado."""

    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(description="UUID do usuário")
    email: str = Field(description="Email do usuário (decifrado)")
    full_name: str = Field(description="Nome completo ou identificador parcial")
    role: str = Field(description="Papel do usuário na plataforma")
    tenant_id: str = Field(description="UUID da empresa")
    is_active: bool = Field(description="Indica se o usuário está ativo")
