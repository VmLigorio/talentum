# Talentum — backend/app/schemas/notification_preference.py
# Responsabilidade: Define os schemas de entrada e saída usados pela validação e documentação da API.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from pydantic import BaseModel, ConfigDict


class NotificationPreferenceResponse(BaseModel):
    """Preferências atuais de envio de notificações do usuário."""

    model_config = ConfigDict(from_attributes=True)

    user_id: int
    action_overdue: bool
    action_due_soon: bool
    goal_overdue: bool
    goal_due_soon: bool
    document_uploaded: bool
    document_review_due: bool
    market_price_alert: bool


class NotificationPreferenceUpdate(BaseModel):
    """Preferências que o usuário deseja alterar."""

    # O schema aceita null explícito, embora as colunas do modelo sejam NOT NULL (achado 50).
    action_overdue: bool | None = None
    action_due_soon: bool | None = None
    goal_overdue: bool | None = None
    goal_due_soon: bool | None = None
    document_uploaded: bool | None = None
    document_review_due: bool | None = None
    market_price_alert: bool | None = None
