# Talentum — backend/app/schemas/client.py
# Responsabilidade: Define os schemas de entrada e saída usados pela validação e documentação da API.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ClientSummary(BaseModel):
    """Dados básicos de identificação e acesso de um cliente."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    role: str
    is_active: bool


class ClientProfileResponse(BaseModel):
    """Dados cadastrais do perfil vinculado à conta do cliente."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    advisor_id: int | None
    phone: str | None
    father_name: str | None
    mother_name: str | None
    address_street: str | None
    address_number: str | None
    address_city: str | None
    address_zip_code: str | None
    address_state: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class ClientPermissionResponse(BaseModel):
    """Permissões concedidas ao cliente para editar suas informações."""

    model_config = ConfigDict(from_attributes=True)

    client_id: int
    can_edit_profile: bool
    can_edit_financial_profile: bool
    can_edit_patrimony: bool
    can_edit_goals: bool
    can_upload_documents: bool


class ClientPermissionUpdate(BaseModel):
    """Campos opcionais para atualizar permissões enviadas pelo assessor."""

    # Omitir mantém o valor atual; null explícito ainda é aceito e pode falhar
    # nas colunas obrigatórias ao persistir (achado 62).
    can_edit_profile: bool | None = None
    can_edit_financial_profile: bool | None = None
    can_edit_patrimony: bool | None = None
    can_edit_goals: bool | None = None
    can_upload_documents: bool | None = None


class ClientDetailResponse(ClientSummary):
    """Resumo da conta combinado com perfil e permissões."""

    profile: ClientProfileResponse | None = None
    permissions: ClientPermissionResponse


class ClientProfileUpdate(BaseModel):
    """Campos cadastrais opcionais aceitos na edição do perfil."""

    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    father_name: str | None = Field(default=None, max_length=120)
    mother_name: str | None = Field(default=None, max_length=120)
    address_street: str | None = Field(default=None, max_length=160)
    address_number: str | None = Field(default=None, max_length=30)
    address_city: str | None = Field(default=None, max_length=100)
    address_zip_code: str | None = Field(default=None, max_length=20)
    address_state: str | None = Field(default=None, max_length=60)


class ClientProfileDataResponse(BaseModel):
    """Visão cadastral detalhada, incluindo o assessor responsável."""

    client_id: int
    name: str
    email: str
    phone: str | None
    father_name: str | None
    mother_name: str | None
    address_street: str | None
    address_number: str | None
    address_city: str | None
    address_zip_code: str | None
    address_state: str | None
    status: str
    advisor_id: int | None
    advisor_name: str | None


class AdvisorSummary(BaseModel):
    """Identificação resumida do assessor vinculado ao cliente."""

    id: int
    name: str
    email: str


class ClientAssignmentUpdate(BaseModel):
    """Alteração do assessor responsável, ou remoção do vínculo."""

    advisor_id: int | None = None


class ClientAssignmentResponse(BaseModel):
    """Assessor atualmente associado ao cliente."""

    client_id: int
    advisor_id: int | None
    advisor_name: str | None


class AuditLogResponse(BaseModel):
    """Evento de auditoria com metadados mínimos e sem payloads pessoais ou financeiros."""

    id: int
    actor_user_id: int | None
    actor_name: str | None
    action: str
    resource: str
    resource_id: str | None
    # Campo legado mantido por compatibilidade; as respostas atuais sempre o omitem.
    details: dict | None = None
    created_at: datetime
