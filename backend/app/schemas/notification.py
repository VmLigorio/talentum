from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    client_id: int
    kind: str
    title: str
    message: str
    read_at: datetime | None
    created_at: datetime
