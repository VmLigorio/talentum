from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.database import get_db
from app.models import ActionItem, FinancialProfile, Goal, PatrimonyItem, User
from app.schemas.dashboard import CategoryTotal, DashboardResponse, GoalProgress
from app.services.authorization import require_client_manager
from app.services.notifications import sync_overdue_notifications


router = APIRouter(prefix="/clients", tags=["dashboard"])
CENT = Decimal("0.01")


def get_client(client_id: int, db: Session) -> User:
    client = db.scalar(select(User).where(User.id == client_id, User.role == "client"))
    if client is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return client


@router.get("/{client_id}/dashboard", response_model=DashboardResponse)
def dashboard(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DashboardResponse:
    get_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    if sync_overdue_notifications(client_id, db):
        db.commit()

    items = list(
        db.scalars(
            select(PatrimonyItem).where(PatrimonyItem.client_id == client_id)
        ).all()
    )
    goals = list(db.scalars(select(Goal).where(Goal.client_id == client_id)).all())
    actions = list(db.scalars(select(ActionItem).where(ActionItem.client_id == client_id)).all())
    profile = db.scalar(
        select(FinancialProfile).where(FinancialProfile.client_id == client_id)
    )
    total = sum((item.value for item in items), Decimal("0"))
    by_category: dict[str, Decimal] = {}
    for item in items:
        by_category[item.category] = by_category.get(item.category, Decimal("0")) + item.value

    categories = [
        CategoryTotal(
            category=category,
            total=value,
            percentage=(value / total * 100).quantize(CENT, rounding=ROUND_HALF_UP)
            if total
            else Decimal("0"),
        )
        for category, value in sorted(by_category.items())
    ]
    goal_progress = [
        GoalProgress(
            id=goal.id,
            title=goal.title,
            target_value=goal.target_value,
            current_value=goal.current_value,
            target_date=goal.target_date,
            percentage=min(
                Decimal("100"),
                (goal.current_value / goal.target_value * 100).quantize(
                    CENT, rounding=ROUND_HALF_UP
                ),
            ),
            status=goal.status,
        )
        for goal in sorted(goals, key=lambda item: (item.status, item.title))
    ]
    action_pending = sum(action.status != "completed" for action in actions)
    action_overdue = sum(
        action.status != "completed" and action.due_date is not None and action.due_date < date.today()
        for action in actions
    )
    return DashboardResponse(
        client_id=client_id,
        patrimony_total=total,
        patrimony_by_category=categories,
        goals=goal_progress,
        monthly_income=profile.monthly_income if profile else None,
        monthly_expenses=profile.monthly_expenses if profile else None,
        action_pending=action_pending,
        action_overdue=action_overdue,
    )
