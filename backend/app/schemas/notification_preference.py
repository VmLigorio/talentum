from pydantic import BaseModel, ConfigDict


class NotificationPreferenceResponse(BaseModel):
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
    action_overdue: bool | None = None
    action_due_soon: bool | None = None
    goal_overdue: bool | None = None
    goal_due_soon: bool | None = None
    document_uploaded: bool | None = None
    document_review_due: bool | None = None
    market_price_alert: bool | None = None
