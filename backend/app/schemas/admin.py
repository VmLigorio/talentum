# Talentum — backend/app/schemas/admin.py
# Responsabilidade: Define os schemas de entrada e saída usados pela validação e documentação da API.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class AdminUserCreate(BaseModel):
    """Dados para um administrador criar uma conta de usuário."""

    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: Literal["advisor", "client"]

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        """Remove espaços externos e converte o e-mail para minúsculas."""
        return value.strip().lower()


class AdminUserStatusUpdate(BaseModel):
    """Novo estado de atividade solicitado para uma conta."""

    is_active: bool


class AdminPasswordReset(BaseModel):
    """Nova senha definida pelo administrador para a conta selecionada."""

    new_password: str = Field(min_length=8, max_length=128)
