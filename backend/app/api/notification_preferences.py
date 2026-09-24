# Talentum — backend/app/api/notification_preferences.py
# Responsabilidade: Expõe endpoints HTTP, valida o usuário atual e orquestra as operações do domínio.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.database import get_db
from app.models import AuditLog, NotificationPreference, User
from app.schemas.notification_preference import (
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
)


router = APIRouter(prefix="/notifications", tags=["notifications"])


def get_or_create_preferences(user_id: int, db: Session) -> NotificationPreference:
    preferences = db.get(NotificationPreference, user_id)
    if preferences is None:
        preferences = NotificationPreference(user_id=user_id)
        db.add(preferences)
        db.commit()
        db.refresh(preferences)
    return preferences


@router.get("/preferences", response_model=NotificationPreferenceResponse)
def get_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationPreference:
    return get_or_create_preferences(current_user.id, db)


@router.patch("/preferences", response_model=NotificationPreferenceResponse)
def update_preferences(
    payload: NotificationPreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NotificationPreference:
    preferences = get_or_create_preferences(current_user.id, db)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(preferences, field, value)
    if changes:
        db.add(
            AuditLog(
                actor_user_id=current_user.id,
                client_user_id=current_user.id if current_user.role == "client" else None,
                action="update",
                resource="notification_preferences",
                resource_id=str(current_user.id),
                details=changes,
            )
        )
    db.commit()
    db.refresh(preferences)
    return preferences
