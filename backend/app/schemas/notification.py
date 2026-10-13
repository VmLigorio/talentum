# Talentum — backend/app/schemas/notification.py
# Responsabilidade: Define os schemas de entrada e saída usados pela validação e documentação da API.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    """Notificação visível ao usuário e informações de leitura."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    client_id: int
    kind: str
    title: str
    message: str
    # O timestamp é por destinatário e fica vazio enquanto o aviso não for lido.
    read_at: datetime | None
    created_at: datetime
