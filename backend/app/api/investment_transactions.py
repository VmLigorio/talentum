# Talentum — backend/app/api/investment_transactions.py
# Registra compras e vendas, mantendo quantidade e custo médio sincronizados.
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.investment_positions import _find_client
from app.db.database import get_db
from app.models import AuditLog, InvestmentPosition, InvestmentTransaction, User
from app.schemas.investment_transaction import (
    InvestmentTransactionCreate,
    InvestmentTransactionResponse,
    InvestmentTransactionVoid,
)
from app.services.authorization import require_client_manager, require_edit_permission


router = APIRouter(prefix="/clients", tags=["investment-transactions"])
MONEY_SCALE = Decimal("0.00000001")


def _scaled(value: Decimal) -> Decimal:
    """Arredonda valores financeiros à escala interna de oito casas decimais."""
    return value.quantize(MONEY_SCALE, rounding=ROUND_HALF_UP)


@router.get(
    "/{client_id}/investment-transactions",
    response_model=list[InvestmentTransactionResponse],
)
def list_investment_transactions(
    client_id: int,
    symbol: str | None = Query(default=None, min_length=1, max_length=32),
    operation_type: str | None = Query(default=None, pattern="^(buy|sell)$"),
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[InvestmentTransaction]:
    """Filtra o histórico do cliente e pagina os lançamentos mais recentes primeiro."""
    _find_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    query = select(InvestmentTransaction).where(
        InvestmentTransaction.client_id == client_id
    )
    if symbol:
        query = query.where(InvestmentTransaction.symbol == symbol.strip().upper())
    if operation_type:
        query = query.where(InvestmentTransaction.operation_type == operation_type)
    if date_from:
        query = query.where(InvestmentTransaction.operation_date >= date_from)
    if date_to:
        query = query.where(InvestmentTransaction.operation_date <= date_to)
    return list(
        db.scalars(
            query.order_by(
                InvestmentTransaction.operation_date.desc(),
                InvestmentTransaction.id.desc(),
            )
            .limit(limit)
            # O offset pode mudar de posição se novas operações entrarem entre páginas.
            .offset(offset)
        ).all()
    )


@router.post(
    "/{client_id}/investment-transactions",
    response_model=InvestmentTransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_investment_transaction(
    client_id: int,
    payload: InvestmentTransactionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvestmentTransaction:
    """Registra compra ou venda e recalcula saldo, custo médio e resultado realizado."""
    _find_client(client_id, db)
    require_edit_permission(client_id, "can_edit_patrimony", current_user, db)

    # Serializa lançamentos do mesmo cliente para não perder compras simultâneas.
    db.scalar(select(User).where(User.id == client_id).with_for_update())
    symbol = payload.symbol.strip().upper()  # A validação de tamanho vem antes do strip; uma compra pode persistir ticker vazio (achado 67).
    positions = list(
        db.scalars(
            select(InvestmentPosition)
            .where(
                InvestmentPosition.client_id == client_id,
                InvestmentPosition.market == payload.market,
                InvestmentPosition.symbol == symbol,
            )
            .order_by(InvestmentPosition.id)
            .with_for_update()
        ).all()
    )
    if len(positions) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Há posições duplicadas deste ativo. Consolide-as antes de registrar operações.",
        )
    # Considera também operações anuladas para não inserir lançamentos antes de eventos já registrados.
    latest_operation = db.scalar(
        select(InvestmentTransaction.operation_date)
        .where(
            InvestmentTransaction.client_id == client_id,
            InvestmentTransaction.market == payload.market,
            InvestmentTransaction.symbol == symbol,
        )
        .order_by(
            InvestmentTransaction.operation_date.desc(),
            InvestmentTransaction.id.desc(),
        )
        .limit(1)
    )
    if latest_operation and payload.operation_date < latest_operation:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Registre as operações em ordem cronológica. A última data deste ativo é {latest_operation:%d/%m/%Y}.",
        )

    position = positions[0] if positions else None
    # Compara a data da operação com created_at.date() sem converter o timestamp para o fuso civil do cliente (achado 52).
    if position and not latest_operation and position.created_at and payload.operation_date < position.created_at.date():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A data não pode anteceder o cadastro do saldo inicial. Para reconstruir todo o histórico, remova a posição inicial e registre as operações em ordem cronológica.",
    )
    quantity_before = position.quantity if position else Decimal("0")
    average_before = position.average_price if position else None
    # Os limites individuais do schema não garantem que o produto caiba em NUMERIC(20,8) (achado 197).
    gross_value = _scaled(payload.quantity * payload.unit_price)
    fees = _scaled(payload.fees)
    # A regra atual assume BRL para B3 e USD para qualquer operação global.
    currency = "BRL" if payload.market == "br" else "USD"
    # Usa o fuso local do processo; datas civis brasileiras podem divergir perto da meia-noite.
    if payload.operation_date > date.today():
        raise HTTPException(status_code=422, detail="A data da operação não pode estar no futuro.")

    # Compras aumentam o saldo e recalculam o preço médio incluindo taxas.
    if payload.operation_type == "buy":
        net_value = _scaled(gross_value + fees)
        quantity_after = quantity_before + payload.quantity
        average_after = _scaled(
            ((quantity_before * (average_before or Decimal("0"))) + net_value)
            / quantity_after
        )
        realized_pnl = None
        if position is None:
            position = InvestmentPosition(
                client_id=client_id,
                symbol=symbol,
                name=payload.name.strip() if payload.name and payload.name.strip() else None,
                market=payload.market,
                quantity=quantity_after,
                average_price=average_after,
                institution=payload.institution.strip() if payload.institution and payload.institution.strip() else None,
                notes="Posição calculada a partir do histórico de operações.",
            )
            db.add(position)
            db.flush()
        else:
            position.quantity = quantity_after
            position.average_price = average_after
            if payload.name and payload.name.strip():
                position.name = payload.name.strip()
            if payload.institution and payload.institution.strip():
                position.institution = payload.institution.strip()
    else:
        # Vendas reduzem o saldo pelo custo médio e não podem exceder cotas disponíveis.
        if fees >= gross_value:
            raise HTTPException(status_code=422, detail="As taxas da venda devem ser menores que o valor bruto.")
        if position is None or quantity_before < payload.quantity:
            available = quantity_before
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Venda maior que o saldo disponível ({available} cotas).",
            )
        net_value = _scaled(gross_value - fees)
        quantity_after = quantity_before - payload.quantity
        average_after = average_before
        realized_pnl = _scaled(net_value - payload.quantity * (average_before or Decimal("0")))
        if quantity_after == 0:
            # A operação mantém símbolo e quantidades de antes/depois; posição encerrada deixa a carteira.
            position_id = None
            db.delete(position)
        else:
            position_id = position.id
            position.quantity = quantity_after
    # Vincula compras à posição corrente; uma venda integral mantém referência nula à linha excluída.
    if payload.operation_type == "buy":
        position_id = position.id if position else None

    # Preserva valores antes/depois para permitir auditoria e futura anulação rastreável.
    transaction = InvestmentTransaction(
        client_id=client_id,
        position_id=position_id,
        created_by_user_id=current_user.id,
        operation_type=payload.operation_type,
        symbol=symbol,
        name=(payload.name.strip() if payload.name and payload.name.strip() else (position.name if position else None)),
        market=payload.market,
        currency=currency,
        operation_date=payload.operation_date,
        quantity=payload.quantity,
        unit_price=payload.unit_price,
        gross_value=gross_value,
        fees=fees,
        net_value=net_value,
        realized_pnl=realized_pnl,
        quantity_before=quantity_before,
        average_price_before=average_before,
        quantity_after=quantity_after,
        average_price_after=average_after if quantity_after else None,
        institution=payload.institution.strip() if payload.institution and payload.institution.strip() else (position.institution if position else None),
        notes=payload.notes.strip() if payload.notes and payload.notes.strip() else None,
    )
    db.add(transaction)
    db.flush()
    # A trilha registra a operação sem duplicar os valores financeiros nela.
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            client_user_id=client_id,
            action="create",
            resource="investment_transaction",
            resource_id=str(transaction.id),
        )
    )
    db.commit()
    db.refresh(transaction)
    return transaction


@router.post(
    "/{client_id}/investment-transactions/{transaction_id}/void",
    response_model=InvestmentTransactionResponse,
)
def void_investment_transaction(
    client_id: int,
    transaction_id: int,
    payload: InvestmentTransactionVoid,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvestmentTransaction:
    """Anula um lançamento e reconstrói saldos posteriores em ordem cronológica."""
    if len(payload.reason.strip()) < 10:
        raise HTTPException(status_code=422, detail="O motivo precisa ter pelo menos 10 caracteres.")
    _find_client(client_id, db)
    require_edit_permission(client_id, "can_edit_patrimony", current_user, db)
    # Bloqueia a linha do cliente mesmo quando ainda não existe posição para travar.
    db.scalar(select(User).where(User.id == client_id).with_for_update())
    # Restringe a busca ao cliente informado para não revelar operações de outra conta.
    target = db.scalar(
        select(InvestmentTransaction)
        .where(
            InvestmentTransaction.id == transaction_id,
            InvestmentTransaction.client_id == client_id,
        )
        .with_for_update()
    )
    if target is None:
        raise HTTPException(status_code=404, detail="Operação não encontrada.")
    if target.voided_at is not None:
        raise HTTPException(status_code=409, detail="Esta operação já foi anulada.")

    # Inclui lançamentos anulados para manter o ponto inicial da reconstrução estável.
    history = list(
        db.scalars(
            select(InvestmentTransaction)
            .where(
                InvestmentTransaction.client_id == client_id,
                InvestmentTransaction.market == target.market,
                InvestmentTransaction.symbol == target.symbol,
            )
            .order_by(
                InvestmentTransaction.operation_date,
                InvestmentTransaction.id,
            )
            .with_for_update()
        ).all()
    )
    if not history:
        raise HTTPException(status_code=409, detail="Não foi possível reconstruir o saldo deste ativo.")

    # A primeira operação guarda o saldo inicial; os lançamentos seguintes são recalculados
    # em ordem cronológica para preservar custo médio e resultado após a anulação. Esta
    # reconstrução pressupõe que não houve novo saldo manual após uma liquidação completa;
    # veja o achado 127, pois esse saldo reintroduzido não tem marco próprio no livro.
    quantity = history[0].quantity_before
    average_price = history[0].average_price_before
    # Guarda novos saldos em memória para só atualizar as linhas depois da validação completa.
    recalculated: list[tuple[InvestmentTransaction, Decimal, Decimal | None, Decimal, Decimal | None, Decimal | None]] = []
    for operation in history:
        if operation.id == target.id or operation.voided_at is not None:
            continue
        quantity_before = quantity
        average_before = average_price
        if operation.operation_type == "buy":
            quantity += operation.quantity
            average_price = _scaled(
                (quantity_before * (average_before or Decimal("0")) + operation.net_value)
                / quantity
            )
            realized = None
        else:
            if quantity_before < operation.quantity or average_before is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Esta operação sustenta uma venda posterior. Anule primeiro as vendas posteriores dependentes.",
                )
            quantity -= operation.quantity
            realized = _scaled(operation.net_value - operation.quantity * average_before)
            if quantity == 0:
                average_price = None
        recalculated.append(
            (operation, quantity_before, average_before, quantity, average_price, realized)
        )

    # Localiza a posição final já bloqueada para sincronizar o saldo reconstruído.
    position_rows = list(
        db.scalars(
            select(InvestmentPosition)
            .where(
                InvestmentPosition.client_id == client_id,
                InvestmentPosition.market == target.market,
                InvestmentPosition.symbol == target.symbol,
            )
            .order_by(InvestmentPosition.id)
            .with_for_update()
        ).all()
    )
    if len(position_rows) > 1:
        raise HTTPException(status_code=409, detail="Há posições duplicadas deste ativo; não é possível recalcular o saldo com segurança.")

    target.voided_at = datetime.now(timezone.utc)
    target.voided_by_user_id = current_user.id
    target.void_reason = payload.reason.strip()
    position = position_rows[0] if position_rows else None
    if quantity > 0:
        if average_price is None:
            raise HTTPException(status_code=409, detail="O saldo final não tem custo médio válido.")
        if position is None:
            position = InvestmentPosition(
                client_id=client_id,
                symbol=target.symbol,
                name=target.name,
                market=target.market,
                quantity=quantity,
                average_price=average_price,
                institution=target.institution,
                notes="Posição recalculada após anulação de operação.",
            )
            db.add(position)
            db.flush()
        else:
            position.quantity = quantity
            position.average_price = average_price
        for operation, quantity_before, average_before, quantity_after, average_after, realized in recalculated:
            operation.position_id = position.id
            operation.quantity_before = quantity_before
            operation.average_price_before = average_before
            operation.quantity_after = quantity_after
            operation.average_price_after = average_after
            operation.realized_pnl = realized
        target.position_id = position.id
    else:
        # Sem cotas remanescentes, remove a posição e desvincula todo o histórico do saldo atual.
        if position is not None:
            db.delete(position)
        for operation in history:
            operation.position_id = None
    # A trilha de auditoria confirma a justificativa junto com a reconstrução do saldo.
    # O motivo é texto livre e também passa a compor os detalhes consultáveis do evento.
    db.add(
        AuditLog(
            actor_user_id=current_user.id,
            client_user_id=client_id,
            action="void",
            resource="investment_transaction",
            resource_id=str(target.id),
        )
    )
    db.commit()
    db.refresh(target)
    return target
