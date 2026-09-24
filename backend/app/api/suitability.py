# Talentum — backend/app/api/suitability.py
# Responsabilidade: Expõe o questionário, salva avaliações e permite a revisão pelo Advisor/Admin.
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.database import get_db
from app.models import AuditLog, SuitabilityAssessment, User
from app.schemas.suitability import (
    SuitabilityAssessmentCreate,
    SuitabilityAssessmentResponse,
    SuitabilityQuestionnaireResponse,
    SuitabilityReviewUpdate,
)
from app.services.authorization import require_client_manager, require_roles
from app.services.suitability import (
    OBJECTIVE_LABELS,
    RISK_PROFILES,
    build_recommendation,
    questionnaire_definition,
    score_answers,
)


router = APIRouter(prefix="/clients", tags=["suitability"])


def find_client(client_id: int, db: Session) -> User:
    client = db.scalar(select(User).where(User.id == client_id, User.role == "client"))
    if client is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return client


def assessment_response(assessment: SuitabilityAssessment) -> SuitabilityAssessmentResponse:
    """Converte o registro persistido para o contrato com rótulos amigáveis."""

    risk = RISK_PROFILES[assessment.risk_profile]
    return SuitabilityAssessmentResponse(
        id=assessment.id,
        client_id=assessment.client_id,
        objective=assessment.objective,
        objective_label=OBJECTIVE_LABELS[assessment.objective],
        risk_profile=assessment.risk_profile,
        risk_profile_label=risk["label"],
        risk_profile_description=risk["description"],
        score=assessment.score,
        answers=assessment.answers,
        recommendation=assessment.recommendation,
        status=assessment.status,
        created_at=assessment.created_at,
        expires_at=assessment.expires_at,
        reviewed_at=assessment.reviewed_at,
        reviewed_by_user_id=assessment.reviewed_by_user_id,
    )


def latest_assessment(client_id: int, db: Session) -> SuitabilityAssessment | None:
    return db.scalar(
        select(SuitabilityAssessment)
        .where(SuitabilityAssessment.client_id == client_id)
        .order_by(SuitabilityAssessment.created_at.desc(), SuitabilityAssessment.id.desc())
        .limit(1)
    )


@router.get("/me/suitability/questionnaire", response_model=SuitabilityQuestionnaireResponse)
def get_my_questionnaire(
    current_user: User = Depends(get_current_user),
) -> dict:
    if current_user.role != "client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="O questionário está disponível para contas de cliente",
        )
    return questionnaire_definition()


@router.get("/me/suitability", response_model=SuitabilityAssessmentResponse | None)
def get_my_suitability(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SuitabilityAssessmentResponse | None:
    if current_user.role != "client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A avaliação está disponível para contas de cliente",
        )
    assessment = latest_assessment(current_user.id, db)
    return assessment_response(assessment) if assessment else None


@router.post(
    "/me/suitability",
    response_model=SuitabilityAssessmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_my_suitability(
    payload: SuitabilityAssessmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SuitabilityAssessmentResponse:
    if current_user.role != "client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente clientes podem responder o questionário",
        )
    try:
        score, risk_profile = score_answers(payload.objective, payload.answers)
        recommendation = build_recommendation(payload.objective, risk_profile)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    previous = latest_assessment(current_user.id, db)
    if previous and previous.status in {"pending_review", "approved"}:
        previous.status = "superseded"

    assessment = SuitabilityAssessment(
        client_id=current_user.id,
        objective=payload.objective,
        risk_profile=risk_profile,
        score=score,
        answers=payload.answers,
        recommendation=recommendation,
        status="pending_review",
        expires_at=datetime.now(timezone.utc) + timedelta(days=365),
    )
    db.add(assessment)
    db.flush()
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            client_user_id=current_user.id,
            action="create",
            resource="suitability_assessment",
            resource_id=str(assessment.id),
            details={"objective": payload.objective, "risk_profile": risk_profile},
        )
    )
    db.commit()
    db.refresh(assessment)
    return assessment_response(assessment)


@router.get("/{client_id}/suitability", response_model=SuitabilityAssessmentResponse | None)
def get_client_suitability(
    client_id: int,
    current_user: User = Depends(require_roles("admin", "advisor")),
    db: Session = Depends(get_db),
) -> SuitabilityAssessmentResponse | None:
    find_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    assessment = latest_assessment(client_id, db)
    return assessment_response(assessment) if assessment else None


@router.post(
    "/{client_id}/suitability/{assessment_id}/review",
    response_model=SuitabilityAssessmentResponse,
)
def review_client_suitability(
    client_id: int,
    assessment_id: int,
    payload: SuitabilityReviewUpdate,
    current_user: User = Depends(require_roles("admin", "advisor")),
    db: Session = Depends(get_db),
) -> SuitabilityAssessmentResponse:
    find_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    assessment = db.scalar(
        select(SuitabilityAssessment).where(
            SuitabilityAssessment.id == assessment_id,
            SuitabilityAssessment.client_id == client_id,
        )
    )
    if assessment is None:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")
    assessment.status = "approved" if payload.approved else "rejected"
    assessment.reviewed_at = datetime.now(timezone.utc)
    assessment.reviewed_by_user_id = current_user.id
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            client_user_id=client_id,
            action="review",
            resource="suitability_assessment",
            resource_id=str(assessment.id),
            details={"approved": payload.approved},
        )
    )
    db.commit()
    db.refresh(assessment)
    return assessment_response(assessment)

