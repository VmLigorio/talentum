# Talentum — backend/app/api/reports.py
# Responsabilidade: Expõe endpoints HTTP, valida o usuário atual e orquestra as operações do domínio.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.database import get_db
from app.models import AuditLog, Report, User
from app.schemas.report import ReportCreate, ReportResponse, ReportUpdate
from app.services.authorization import require_client_manager, require_roles


router = APIRouter(prefix="/clients", tags=["reports"])


def find_client(client_id: int, db: Session) -> User:
    """Localiza uma conta de cliente ou retorna erro 404."""
    client = db.scalar(select(User).where(User.id == client_id, User.role == "client"))
    if client is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return client


def find_report(client_id: int, report_id: int, db: Session) -> Report:
    """Busca um relatório dentro do cliente informado ou retorna erro 404."""
    report = db.scalar(
        select(Report).where(Report.id == report_id, Report.client_id == client_id)
    )
    if report is None:
        raise HTTPException(status_code=404, detail="Relatório não encontrado")
    return report


@router.get("/{client_id}/reports", response_model=list[ReportResponse])
def list_reports(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Report]:
    """Lista relatórios autorizados, ocultando rascunhos do cliente final."""
    find_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    query = select(Report).where(Report.client_id == client_id)
    if current_user.role == "client":
        query = query.where(Report.status == "published")
    return list(db.scalars(query.order_by(Report.period_end.desc())).all())


@router.get("/{client_id}/reports/{report_id}", response_model=ReportResponse)
def get_report(
    client_id: int,
    report_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Report:
    """Retorna um relatório e oculta rascunhos de usuários clientes."""
    find_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    report = find_report(client_id, report_id, db)
    if current_user.role == "client" and report.status != "published":
        raise HTTPException(status_code=404, detail="Relatório não encontrado")
    return report


@router.post("/{client_id}/reports", response_model=ReportResponse, status_code=201)
def create_report(
    client_id: int,
    payload: ReportCreate,
    current_user: User = Depends(require_roles("admin", "advisor")),
    db: Session = Depends(get_db),
) -> Report:
    """Cria um relatório e registra a data caso já seja publicado."""
    find_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    # O schema valida o comprimento, mas título e resumo não são normalizados nesta rota.
    report = Report(client_id=client_id, **payload.model_dump())
    if report.status == "published":
        report.published_at = datetime.now(timezone.utc)
    db.add(report)
    db.flush()
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            client_user_id=client_id,
            action="create",
            resource="report",
            resource_id=str(report.id),
        )
    )
    db.commit()
    db.refresh(report)
    return report


@router.patch("/{client_id}/reports/{report_id}", response_model=ReportResponse)
def update_report(
    client_id: int,
    report_id: int,
    payload: ReportUpdate,
    current_user: User = Depends(require_roles("admin", "advisor")),
    db: Session = Depends(get_db),
) -> Report:
    """Atualiza um relatório e define a primeira data de publicação."""
    find_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    report = find_report(client_id, report_id, db)
    # O PATCH aplica chaves presentes, inclusive null; valores omitidos são preservados.
    # Textos enviados são atribuídos como chegaram, sem remover espaços nas extremidades.
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(report, field, value)
    # Registra a primeira publicação; se houver data anterior, uma republicação a preserva.
    if report.status == "published" and report.published_at is None:
        report.published_at = datetime.now(timezone.utc)
    record = AuditLog(
        actor_user_id=current_user.id,
        client_user_id=client_id,
        action="update",
        resource="report",
        resource_id=str(report.id),
    )
    db.add(record)
    db.commit()
    db.refresh(report)
    return report


@router.delete("/{client_id}/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_report(
    client_id: int,
    report_id: int,
    current_user: User = Depends(require_roles("admin", "advisor")),
    db: Session = Depends(get_db),
) -> None:
    """Remove somente rascunhos e preserva relatórios já publicados."""
    find_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    report = find_report(client_id, report_id, db)
    if report.status == "published":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Relatórios publicados não podem ser removidos",
        )
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            client_user_id=client_id,
            action="delete",
            resource="report",
            resource_id=str(report.id),
        )
    )
    db.delete(report)
    db.commit()
