# Talentum — backend/app/schemas/auth.py
# Responsabilidade: Define os schemas de entrada e saída usados pela validação e documentação da API.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginRequest(BaseModel):
    """Credenciais informadas para iniciar uma sessão."""

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        """Remove espaços externos e converte o e-mail para minúsculas após a validação do campo."""
        return value.strip().lower()


class RefreshRequest(BaseModel):
    """Token renovável apresentado para obter novos tokens."""

    refresh_token: str = Field(min_length=1)


class PasswordChangeRequest(BaseModel):
    """Senha atual e nova senha solicitadas na troca de credencial."""

    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class TokenResponse(BaseModel):
    """Tokens e prazo de validade devolvidos após autenticação."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    """Identificação pública da conta autenticada."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    role: str
    is_active: bool
