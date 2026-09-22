from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    client_id: int
    uploaded_by_user_id: int
    original_name: str
    content_type: str
    kind: str
    size_bytes: int
    description: str | None
    created_at: datetime
