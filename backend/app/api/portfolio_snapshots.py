from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.investment_positions import _find_client
from app.db.database import get_db
from app.models import PortfolioSnapshot, User
from app.schemas.portfolio_snapshot import PortfolioSnapshotResponse
from app.services.authorization import require_client_manager
from app.services.portfolio_snapshots import capture_client_snapshots


router = APIRouter(prefix="/clients", tags=["portfolio-snapshots"])


def _list_snapshots(client_id: int, db: Session, limit: int, currency: str | None) -> list[PortfolioSnapshot]:
    query = select(PortfolioSnapshot).where(PortfolioSnapshot.client_id == client_id)
    if currency:
        query = query.where(PortfolioSnapshot.currency == currency.upper())
    latest = list(
        db.scalars(
            query.order_by(PortfolioSnapshot.captured_at.desc()).limit(limit)
        ).all()
    )
    return list(reversed(latest))


@router.get("/{client_id}/investment-snapshots", response_model=list[PortfolioSnapshotResponse])
def get_investment_snapshots(
    client_id: int,
    limit: int = Query(default=90, ge=1, le=365),
    currency: str | None = Query(default=None, min_length=3, max_length=10),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PortfolioSnapshot]:
    _find_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    return _list_snapshots(client_id, db, limit, currency)


@router.post(
    "/{client_id}/investment-snapshots/capture",
    response_model=list[PortfolioSnapshotResponse],
    status_code=status.HTTP_201_CREATED,
)
def capture_investment_snapshots(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PortfolioSnapshot]:
    _find_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    snapshots = capture_client_snapshots(client_id, db)
    db.commit()
    for snapshot in snapshots:
        db.refresh(snapshot)
    return snapshots
