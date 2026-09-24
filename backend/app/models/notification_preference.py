# Talentum — backend/app/models/notification_preference.py
# Responsabilidade: Define os modelos ORM que representam as entidades persistidas no banco de dados.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from sqlalchemy import Boolean, ForeignKey, Integer, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    action_overdue: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    action_due_soon: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    goal_overdue: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    goal_due_soon: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    document_uploaded: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    document_review_due: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    market_price_alert: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
