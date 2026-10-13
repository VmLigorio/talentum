# Talentum — backend/app/api/suitability.py
# Responsabilidade: Expõe o questionário, salva avaliações e permite a revisão pelo Advisor/Admin.
import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.database import get_db
from app.models import (
    AuditLog,
    FinancialProfile,
    Goal,
    PatrimonyItem,
    SuitabilityAssessment,
    User,
)
from app.schemas.suitability import (
    SuitabilityAssessmentCreate,
    SuitabilityAssessmentResponse,
    SuitabilityAdvisorProposalUpdate,
    SuitabilityClientResponseUpdate,
    SuitabilityQuestionnaireResponse,
    SuitabilityReviewUpdate,
)
from app.services.authorization import require_client_manager, require_roles
from app.services.suitability import (
    OBJECTIVE_LABELS,
    RISK_PROFILES,
    build_recommendation,
    questionnaire_definition,
    build_knowledge_review_flags,
    build_recommended_actions,
    score_answers,
)


router = APIRouter(prefix="/clients", tags=["suitability"])


def find_client(client_id: int, db: Session) -> User:
    """Localiza uma conta de cliente ou retorna erro 404."""
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
        financial_situation=getattr(assessment, "financial_situation_snapshot", None),
        recommendation=assessment.recommendation,
        status=assessment.status,
        client_response=assessment.client_response,
        client_response_note=assessment.client_response_note,
        client_response_at=assessment.client_response_at,
        created_at=assessment.created_at,
        expires_at=assessment.expires_at,
        reviewed_at=assessment.reviewed_at,
        reviewed_by_user_id=assessment.reviewed_by_user_id,
    )


def _money(value: Decimal | int | None) -> str | None:
    """Formata valores monetários com duas casas sem converter para float."""
    return None if value is None else format(Decimal(value), ".2f")


def build_financial_situation_snapshot(client_id: int, db: Session) -> dict:
    """Cria um retrato versionado dos dados financeiros usados na avaliação."""
    # Busca os dados-base do perfil, do patrimônio e das metas ativas do cliente.
    profile = db.get(FinancialProfile, client_id)
    # Ordena os itens para gerar respostas e versões determinísticas do mesmo estado.
    items = list(
        db.scalars(
            select(PatrimonyItem)
            .where(PatrimonyItem.client_id == client_id)
            .order_by(PatrimonyItem.category, PatrimonyItem.id)
        ).all()
    )
    # Considera apenas metas ativas, ordenadas por prazo e identificador.
    goals = list(
        db.scalars(
            select(Goal)
            .where(Goal.client_id == client_id, Goal.status == "active")
            .order_by(Goal.target_date, Goal.id)
        ).all()
    )

    # Consolida patrimônio por categoria sem converter valores decimais para float.
    by_category: dict[str, Decimal] = {}
    for item in items:
        by_category[item.category] = by_category.get(item.category, Decimal("0")) + item.value
    patrimony_total = sum((item.value for item in items), Decimal("0"))
    monthly_surplus = (
        profile.monthly_income - profile.monthly_expenses if profile is not None else None
    )

    # Seleciona os campos que participam da versão confirmada pelo cliente.
    source_data = {
        "profile": None
        if profile is None
        else {
            "client_id": profile.client_id,
            "monthly_income": _money(profile.monthly_income),
            "monthly_expenses": _money(profile.monthly_expenses),
            "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
        },
        "patrimony": [
            {
                "id": item.id,
                "category": item.category,
                "value": _money(item.value),
                "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            }
            for item in items
        ],
        "goals": [
            {
                "id": goal.id,
                "title": goal.title,
                "target_value": _money(goal.target_value),
                "current_value": _money(goal.current_value),
                "target_date": goal.target_date.isoformat() if goal.target_date else None,
                "updated_at": goal.updated_at.isoformat() if goal.updated_at else None,
            }
            for goal in goals
        ],
    }
    # O hash permite detectar se algum dado usado para confirmar o questionário mudou.
    data_version = hashlib.sha256(
        json.dumps(source_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    # Sinaliza limites de informação e capacidade que exigem revisão do Advisor.
    flags = ["liabilities_not_recorded"]
    if monthly_surplus is not None and monthly_surplus <= 0:
        flags.append("monthly_surplus_not_positive")
    if not items:
        flags.append("no_patrimony_items_recorded")
    # Usa uma janela fixa de 730 dias a partir da data civil UTC para sinalizar metas próximas.
    today = datetime.now(timezone.utc).date()
    if any(goal.target_date and goal.target_date <= today + timedelta(days=730) for goal in goals):
        flags.append("active_goal_within_2_years")

    # Entrega o retrato exibido na confirmação e usado para contextualizar a avaliação.
    return {
        "data_version": data_version,
        "snapshot_at": datetime.now(timezone.utc).isoformat(),
        "has_financial_profile": profile is not None,
        "financial_profile_updated_at": (
            profile.updated_at.isoformat()
            if profile is not None and profile.updated_at is not None
            else None
        ),
        "monthly_income": _money(profile.monthly_income) if profile else None,
        "monthly_expenses": _money(profile.monthly_expenses) if profile else None,
        "monthly_surplus": _money(monthly_surplus),
        "patrimony_total": _money(patrimony_total) or "0.00",
        "patrimony_by_category": [
            {"category": category, "value": _money(value) or "0.00"}
            for category, value in sorted(by_category.items())
        ],
        "patrimony_items_count": len(items),
        "active_goals": [
            {
                "title": goal.title,
                "target_value": _money(goal.target_value) or "0.00",
                "current_value": _money(goal.current_value) or "0.00",
                "target_date": goal.target_date.isoformat() if goal.target_date else None,
            }
            for goal in goals
        ],
        "capacity_flags": flags,
        "client_confirmed_at": None,
    }


def latest_assessment(client_id: int, db: Session) -> SuitabilityAssessment | None:
    """Busca a avaliação mais recente, usando o identificador em caso de empate."""
    return db.scalar(
        select(SuitabilityAssessment)
        .where(SuitabilityAssessment.client_id == client_id)
        .order_by(SuitabilityAssessment.created_at.desc(), SuitabilityAssessment.id.desc())
        .limit(1)
    )


@router.get("/me/suitability/questionnaire", response_model=SuitabilityQuestionnaireResponse)
def get_my_questionnaire(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Entrega o questionário junto do retrato financeiro atual do cliente."""
    if current_user.role != "client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="O questionário está disponível para contas de cliente",
        )
    definition = questionnaire_definition()
    definition["financial_situation"] = build_financial_situation_snapshot(current_user.id, db)
    return definition


@router.get("/me/suitability", response_model=SuitabilityAssessmentResponse | None)
def get_my_suitability(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SuitabilityAssessmentResponse | None:
    """Retorna a avaliação mais recente da conta autenticada."""
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
    """Valida respostas e contexto, calcula a recomendação e salva a avaliação."""
    if current_user.role != "client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente clientes podem responder o questionário",
        )
    # Exige confirmação do retrato financeiro atual antes de calcular o perfil.
    try:
        if not payload.confirm_financial_situation:
            raise HTTPException(
                status_code=422,
                detail="Confirme os dados financeiros exibidos antes de gerar a avaliação",
            )
        # Recalcula o contexto no servidor para não confiar apenas nos dados enviados pela tela.
        financial_situation = build_financial_situation_snapshot(current_user.id, db)
        if not financial_situation["has_financial_profile"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Peça ao Advisor para cadastrar seu perfil financeiro antes de continuar",
            )
        # Recusa a resposta se os dados mudaram desde que o cliente os confirmou.
        if payload.financial_data_version != financial_situation["data_version"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Os dados financeiros mudaram. Atualize a tela e confirme novamente",
            )
        financial_situation["client_confirmed_at"] = datetime.now(timezone.utc).isoformat()
        # Calcula o perfil e monta o modelo da carteira a partir do objetivo e das respostas.
        score, risk_profile = score_answers(payload.objective, payload.answers)
        recommendation = build_recommendation(
            payload.objective, risk_profile, financial_situation
        )
        # Anexa alertas de familiaridade e etapas de revisão à proposta educativa.
        recommendation["knowledge_review_flags"] = build_knowledge_review_flags(
            payload.answers, recommendation
        )
        recommendation["recommended_actions"] = build_recommended_actions(
            payload.objective,
            payload.answers,
            financial_situation,
            recommendation["knowledge_review_flags"],
        )
        if recommendation["knowledge_review_flags"]:
            recommendation["guardrails"].append(
                "Revise familiaridade, histórico de operações e formação relatados antes de validar os produtos sugeridos."
            )
    # Mantém erros HTTP deliberados e converte erros de domínio em validação 422.
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Substitui a avaliação mais recente na mesma transação em que cria a nova.
    previous = latest_assessment(current_user.id, db)
    if previous and previous.status in {"pending_review", "approved"}:
        previous.status = "superseded"

    # Persiste respostas, retrato confirmado, recomendação e prazo na mesma avaliação.
    assessment = SuitabilityAssessment(
        client_id=current_user.id,
        objective=payload.objective,
        risk_profile=risk_profile,
        score=score,
        answers=payload.answers,
        financial_situation_snapshot=financial_situation,
        recommendation=recommendation,
        status="pending_review",
        expires_at=datetime.now(timezone.utc) + timedelta(days=365),
    )
    db.add(assessment)
    # Atualiza o perfil financeiro existente para que o Advisor veja o resultado do questionário.
    financial_profile = db.get(FinancialProfile, current_user.id)
    if financial_profile is not None:
        financial_profile.risk_profile = risk_profile
    # Gera o ID da avaliação para vincular o evento de auditoria antes do commit.
    db.flush()
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            client_user_id=current_user.id,
            action="create",
            resource="suitability_assessment",
            resource_id=str(assessment.id),
        )
    )
    # Confirma a avaliação, o perfil financeiro e a auditoria na mesma transação.
    db.commit()
    db.refresh(assessment)
    return assessment_response(assessment)


@router.post(
    "/me/suitability/{assessment_id}/response",
    response_model=SuitabilityAssessmentResponse,
)
def respond_to_my_suitability(
    assessment_id: int,
    payload: SuitabilityClientResponseUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SuitabilityAssessmentResponse:
    """Registra aceite, recusa ou pedido de ajuste do cliente."""
    if current_user.role != "client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente clientes podem responder à carteira sugerida",
        )
    # A leitura não bloqueia respostas simultâneas; ambas podem confirmar e gravar auditoria.
    assessment = db.scalar(
        select(SuitabilityAssessment).where(
            SuitabilityAssessment.id == assessment_id,
            SuitabilityAssessment.client_id == current_user.id,
        )
    )
    if assessment is None:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")
    # Confere o status, mas não compara o retrato com o perfil financeiro atual (achado 128).
    if assessment.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A carteira precisa ser aprovada pelo Advisor antes da resposta do cliente",
        )
    # O aceite exige proposta personalizada publicada; recusa e pedido de ajuste também são registrados.
    if payload.response == "accepted" and not assessment.recommendation.get(
        "advisor_proposal_published_at"
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O Advisor ainda não publicou uma sugestão personalizada para esta carteira",
        )
    if assessment.client_response != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta carteira já recebeu uma resposta do cliente",
        )

    assessment.client_response = payload.response
    assessment.client_response_note = payload.note.strip() if payload.note else None
    assessment.client_response_at = datetime.now(timezone.utc)
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            client_user_id=current_user.id,
            action="respond",
            resource="suitability_assessment",
            resource_id=str(assessment.id),
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
    """Permite ao assessor responsável consultar a avaliação do cliente."""
    find_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    assessment = latest_assessment(client_id, db)
    return assessment_response(assessment) if assessment else None


@router.put(
    "/{client_id}/suitability/{assessment_id}/proposal",
    response_model=SuitabilityAssessmentResponse,
)
def publish_client_suitability_proposal(
    client_id: int,
    assessment_id: int,
    payload: SuitabilityAdvisorProposalUpdate,
    current_user: User = Depends(require_roles("admin", "advisor")),
    db: Session = Depends(get_db),
) -> SuitabilityAssessmentResponse:
    """Publica ativos escolhidos pelo assessor na recomendação pendente."""
    # Confirma o vínculo do assessor e localiza a avaliação dentro do cliente autorizado.
    find_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    assessment = db.scalar(
        select(SuitabilityAssessment).where(
            SuitabilityAssessment.id == assessment_id,
            SuitabilityAssessment.client_id == client_id,
        )
    )
    # Bloqueia avaliações inexistentes, encerradas, vencidas ou já aceitas pelo cliente.
    if assessment is None:
        raise HTTPException(status_code=404, detail="Avaliação não encontrada")
    # A publicação também não revalida a versão financeira salva na avaliação (achado 128).
    if assessment.status in {"rejected", "superseded"} or assessment.expires_at <= datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta avaliação não está mais disponível para publicação",
        )
    if assessment.client_response == "accepted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O cliente já aceitou esta sugestão",
        )

    # Exige que a proposta mantenha exatamente as classes previstas pelo modelo original.
    recommendation = assessment.recommendation or {}
    current_allocations = recommendation.get("allocations", [])
    valid_classes = {item.get("asset_class") for item in current_allocations}
    proposal_classes = [item.asset_class for item in payload.allocations]
    if len(proposal_classes) != len(set(proposal_classes)) or set(proposal_classes) != valid_classes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Inclua cada categoria da carteira uma única vez",
        )

    # Agrupa os ativos por categoria e impede proposta vazia ou símbolos repetidos na categoria.
    # A API valida o formato, mas não confirma ticker e metadados na fonte de mercado (achado 183).
    assets_by_class = {item.asset_class: item.assets for item in payload.allocations}
    all_assets = [asset for assets in assets_by_class.values() for asset in assets]
    if not all_assets:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Adicione ao menos um ativo antes de publicar a sugestão",
        )
    # A chave de duplicidade é verificada por categoria; o mesmo ativo pode aparecer em classes distintas.
    for assets in assets_by_class.values():
        keys = [(asset.market, asset.symbol.casefold()) for asset in assets]
        if len(keys) != len(set(keys)):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Não repita o mesmo ativo na mesma categoria",
            )

    # Incorpora as escolhas do assessor sem substituir percentuais e justificativas do modelo.
    now = datetime.now(timezone.utc)
    updated_allocations = []
    for allocation in current_allocations:
        updated_allocations.append(
            {
                **allocation,
                "advisor_assets": [
                    asset.model_dump(exclude_none=True)
                    for asset in assets_by_class[allocation["asset_class"]]
                ],
            }
        )
    # Registra a revisão e devolve a avaliação ao estado pendente de resposta do cliente.
    assessment.recommendation = {
        **recommendation,
        "allocations": updated_allocations,
        "advisor_proposal_published_at": now.isoformat(),
        "advisor_proposal_by": current_user.name,
    }
    assessment.status = "approved"
    assessment.reviewed_at = now
    assessment.reviewed_by_user_id = current_user.id
    if assessment.client_response != "pending":
        assessment.client_response = "pending"
        assessment.client_response_note = None
        assessment.client_response_at = None
    # Audita as categorias e símbolos publicados antes de persistir a avaliação.
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            client_user_id=client_id,
            action="publish",
            resource="suitability_advisor_proposal",
            resource_id=str(assessment.id),
        )
    )
    db.commit()
    db.refresh(assessment)
    return assessment_response(assessment)


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
    """Aprova ou rejeita a avaliação do cliente e registra a revisão."""
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
    if assessment.client_response == "accepted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A avaliação já foi aceita pelo cliente e não pode ser alterada",
        )
    # A decisão atualiza o estado e o responsável pela revisão na mesma transação.
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
        )
    )
    db.commit()
    db.refresh(assessment)
    return assessment_response(assessment)
