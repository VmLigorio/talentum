# Talentum — backend/app/api/investment_positions.py
# Responsabilidade: Expõe endpoints HTTP, valida o usuário atual e orquestra as operações do domínio.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from decimal import Decimal, ROUND_HALF_UP

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.database import get_db
from app.models import AuditLog, InvestmentPosition, InvestmentTransaction, User
from app.schemas.investment_position import (
    InvestmentAllocation,
    InvestmentCurrencyTotal,
    InvestmentPortfolioResponse,
    InvestmentPositionCreate,
    InvestmentPositionResponse,
    InvestmentPositionUpdate,
)
from app.services.authorization import require_client_manager, require_edit_permission
from app.services.market_data import MarketDataService


router = APIRouter(prefix="/clients", tags=["investment-positions"])
CENT = Decimal("0.01")


def _find_client(client_id: int, db: Session) -> User:
    """Confirma que o identificador pertence a um usuário com perfil de cliente."""
    client = db.scalar(select(User).where(User.id == client_id, User.role == "client"))
    if client is None:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return client


def _audit(db: Session, actor: User, client_id: int, action: str, item_id: int | None = None) -> None:
    """Agenda um registro de auditoria para a alteração da posição patrimonial."""
    db.add(
        AuditLog(
            actor_user_id=actor.id,
            client_user_id=client_id,
            action=action,
            resource="investment_position",
            resource_id=str(item_id) if item_id is not None else None,
        )
    )


def _quote(item: InvestmentPosition, service: MarketDataService) -> tuple[str | None, Decimal | None, str | None, str | None]:
    """Consulta a cotação do ativo e converte o preço para Decimal com segurança."""
    try:
        instrument = service.details(item.symbol, item.market)
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        return None, None, None, None
    price = Decimal(str(instrument.price)) if instrument.price is not None else None
    return instrument.name, price, instrument.currency, instrument.source


def _position_response(
    item: InvestmentPosition,
    service: MarketDataService,
    current_total: Decimal,
    quote: tuple[str | None, Decimal | None, str | None, str | None] | None = None,
) -> InvestmentPositionResponse:
    """Calcula valor atual, lucro, percentual e peso sem misturar moedas."""
    # Usa quantidade e preço médio de compra para preservar o custo originalmente registrado.
    invested = item.quantity * item.average_price
    # Consulta o provedor, reaproveita cotação fornecida pelo chamador e mantém o nome manual preferencial.
    quoted_name, current_price, currency, source = quote or _quote(item, service)
    name = item.name or quoted_name
    currency = currency or ("BRL" if item.market == "br" else "USD")
    # Sem preço confiável, deixa valor atual e resultado indisponíveis em vez de estimá-los.
    current_value = item.quantity * current_price if current_price is not None else None
    pnl = current_value - invested if current_value is not None else None
    # Calcula retorno e participação apenas quando há base válida; o total recebido usa a mesma moeda.
    pnl_percent = (pnl / invested * 100).quantize(CENT, rounding=ROUND_HALF_UP) if pnl is not None and invested else None
    allocation = (current_value / current_total * 100).quantize(CENT, rounding=ROUND_HALF_UP) if current_value is not None and current_total else Decimal("0")
    return InvestmentPositionResponse(
        id=item.id,
        client_id=item.client_id,
        symbol=item.symbol,
        market=item.market,
        quantity=item.quantity,
        average_price=item.average_price,
        institution=item.institution,
        notes=item.notes,
        created_at=item.created_at,
        updated_at=item.updated_at,
        name=name,
        current_price=current_price,
        currency=currency,
        source=source,
        invested_value=invested,
        current_value=current_value,
        pnl=pnl,
        pnl_percent=pnl_percent,
        allocation_percent=allocation,
    )


def _load_positions(client_id: int, db: Session) -> list[InvestmentPosition]:
    """Carrega as posições do cliente em ordem estável de mercado e símbolo."""
    return list(
        db.scalars(
            select(InvestmentPosition)
            .where(InvestmentPosition.client_id == client_id)
            .order_by(InvestmentPosition.market, InvestmentPosition.symbol, InvestmentPosition.id)
        ).all()
    )


def _portfolio(client_id: int, db: Session) -> InvestmentPortfolioResponse:
    """Agrupa posições cotadas por moeda e monta totais e alocações da carteira."""
    items = _load_positions(client_id, db)
    service = MarketDataService()
    quotes: list[tuple[InvestmentPosition, Decimal, Decimal | None, str, tuple[str | None, Decimal | None, str | None, str | None]]] = []
    currency_totals: dict[str, dict[str, Decimal | int]] = {}
    # Busca cotações e acumula totais separadamente para cada moeda.
    for item in items:
        invested = item.quantity * item.average_price
        quote = _quote(item, service)
        _, price, quote_currency, _ = quote
        currency = quote_currency or ("BRL" if item.market == "br" else "USD")
        current_value = item.quantity * price if price is not None else None
        totals = currency_totals.setdefault(currency, {"invested": Decimal("0"), "current": Decimal("0"), "pnl": Decimal("0"), "count": 0, "priced_count": 0})
        # O custo investido inclui todas as posições, mesmo as que não têm cotação atual.
        totals["invested"] += invested
        totals["count"] += 1
        if current_value is not None:
            # Valor atual e resultado incluem somente posições cotadas; o percentual abaixo ainda usa o custo total.
            totals["current"] += current_value
            totals["pnl"] += current_value - invested
            totals["priced_count"] += 1
        quotes.append((item, invested, current_value, currency, quote))

    # Os pesos são relativos ao total da moeda do ativo; moedas diferentes nunca são somadas.
    # Converte os valores acumulados para respostas individuais e pesos por mercado.
    positions = []
    allocation_values: dict[tuple[str, str], Decimal] = {}
    for item, _, current_value, currency, quote in quotes:
        if current_value is not None:
            allocation_values[(item.market, currency)] = allocation_values.get((item.market, currency), Decimal("0")) + current_value
        positions.append(_position_response(item, service, currency_totals[currency]["current"], quote))
    allocations = [
        InvestmentAllocation(
            market=market,
            label=("Brasil — B3" if market == "br" else "Exterior") + " · " + currency,
            currency=currency,
            value=value,
            percentage=(value / currency_totals[currency]["current"] * 100).quantize(CENT, rounding=ROUND_HALF_UP) if currency_totals[currency]["current"] else Decimal("0"),
        )
        for (market, currency), value in allocation_values.items()
        if value or not items
    ]
    currency_totals_response = [
        InvestmentCurrencyTotal(
            currency=currency,
            invested_total=data["invested"],
            current_total=data["current"],
            pnl_total=data["pnl"],
            pnl_percent=(data["pnl"] / data["invested"] * 100).quantize(CENT, rounding=ROUND_HALF_UP) if data["priced_count"] and data["invested"] else None,
            position_count=data["count"],
        )
        for currency, data in sorted(currency_totals.items())
    ]
    total_currency = next(iter(currency_totals)) if len(currency_totals) == 1 else None
    single = currency_totals.get(total_currency) if total_currency else None
    return InvestmentPortfolioResponse(
        client_id=client_id,
        invested_total=single["invested"] if single else None,
        current_total=single["current"] if single else None,
        priced_invested_total=single["invested"] if single and single["priced_count"] else None,
        pnl_total=single["pnl"] if single else None,
        pnl_percent=(single["pnl"] / single["invested"] * 100).quantize(CENT, rounding=ROUND_HALF_UP) if single and single["priced_count"] and single["invested"] else None,
        total_currency=total_currency,
        mixed_currency=len(currency_totals) > 1,
        currency_totals=currency_totals_response,
        position_count=len(items),
        priced_position_count=sum(current_value is not None for _, _, current_value, _, _ in quotes),
        unpriced_position_count=sum(current_value is None for _, _, current_value, _, _ in quotes),
        allocations=allocations,
        positions=positions,
    )


@router.get("/{client_id}/investment-portfolio", response_model=InvestmentPortfolioResponse)
def get_investment_portfolio(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvestmentPortfolioResponse:
    """Retorna a carteira após validar existência e permissão de consulta."""
    _find_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    return _portfolio(client_id, db)


@router.post("/{client_id}/investment-positions", response_model=InvestmentPositionResponse, status_code=status.HTTP_201_CREATED)
def create_investment_position(
    client_id: int,
    payload: InvestmentPositionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvestmentPositionResponse:
    """Cadastra uma posição inicial, impedindo ativos duplicados no mesmo mercado."""
    _find_client(client_id, db)
    require_edit_permission(client_id, "can_edit_patrimony", current_user, db)
    symbol = payload.symbol.strip().upper()  # A validação de tamanho vem antes do strip; espaços podem virar símbolo vazio (achado 67).
    # Esta pré-consulta evita duplicatas sequenciais, mas não protege gravações concorrentes no banco;
    # ao contrário da rota de operações, este cadastro também não bloqueia a linha do cliente.
    duplicate = db.scalar(
        select(InvestmentPosition.id).where(
            InvestmentPosition.client_id == client_id,
            InvestmentPosition.market == payload.market,
            InvestmentPosition.symbol == symbol,
        )
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="Este ativo já tem uma posição cadastrada. Registre uma compra ou venda no histórico de operações.")
    item = InvestmentPosition(
        client_id=client_id,
        symbol=symbol,
        name=payload.name.strip() if payload.name and payload.name.strip() else None,
        market=payload.market,
        quantity=payload.quantity,
        average_price=payload.average_price,
        institution=payload.institution.strip() if payload.institution and payload.institution.strip() else None,
        notes=payload.notes.strip() if payload.notes and payload.notes.strip() else None,
    )
    db.add(item)
    db.flush()
    _audit(db, current_user, client_id, "create", item.id)
    db.commit()
    db.refresh(item)
    # Sem o total consolidado, a resposta de mutação calcula a alocação como zero.
    return _position_response(item, MarketDataService(), Decimal("0"))


@router.patch("/{client_id}/investment-positions/{position_id}", response_model=InvestmentPositionResponse)
def update_investment_position(
    client_id: int,
    position_id: int,
    payload: InvestmentPositionUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> InvestmentPositionResponse:
    """Atualiza dados cadastrais e protege saldos que já têm operações vinculadas."""
    _find_client(client_id, db)
    require_edit_permission(client_id, "can_edit_patrimony", current_user, db)
    item = db.scalar(
        select(InvestmentPosition).where(
            InvestmentPosition.id == position_id,
            InvestmentPosition.client_id == client_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Posição de investimento não encontrada")
    updates = payload.model_dump(exclude_unset=True)
    # exclude_unset preserva null explícito; campos opcionais do schema podem chegar como None às colunas obrigatórias.
    has_transactions = db.scalar(
        select(InvestmentTransaction.id)
        .where(InvestmentTransaction.position_id == item.id)
        .limit(1)
    ) is not None
    if has_transactions and {"symbol", "market", "quantity", "average_price"}.intersection(updates):
        raise HTTPException(
            status_code=409,
            detail="Esta posição já tem operações registradas. Altere o saldo registrando uma compra ou venda.",
        )
    if "symbol" in updates and isinstance(updates["symbol"], str):
        updates["symbol"] = updates["symbol"].strip().upper()
    if "symbol" in updates or "market" in updates:
        # A checagem prévia não substitui uma constraint única capaz de serializar gravações concorrentes.
        duplicate = db.scalar(
            select(InvestmentPosition.id).where(
                InvestmentPosition.client_id == client_id,
                InvestmentPosition.id != item.id,
                InvestmentPosition.market == updates.get("market", item.market),
                InvestmentPosition.symbol == updates.get("symbol", item.symbol),
            )
        )
        if duplicate is not None:
            raise HTTPException(status_code=409, detail="Este ativo já tem outra posição cadastrada.")
    for field, value in updates.items():
        setattr(item, field, value.strip() if isinstance(value, str) and value.strip() else (None if isinstance(value, str) else value))
    _audit(db, current_user, client_id, "update", item.id)
    db.commit()
    db.refresh(item)
    # Sem o total consolidado, a resposta de mutação calcula a alocação como zero.
    return _position_response(item, MarketDataService(), Decimal("0"))


@router.delete("/{client_id}/investment-positions/{position_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_investment_position(
    client_id: int,
    position_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    """Remove uma posição sem histórico; posições operadas devem ser encerradas por venda."""
    _find_client(client_id, db)
    require_edit_permission(client_id, "can_edit_patrimony", current_user, db)
    item = db.scalar(
        select(InvestmentPosition).where(
            InvestmentPosition.id == position_id,
            InvestmentPosition.client_id == client_id,
        )
    )
    if item is None:
        raise HTTPException(status_code=404, detail="Posição de investimento não encontrada")
    has_transactions = db.scalar(
        select(InvestmentTransaction.id)
        .where(InvestmentTransaction.position_id == item.id)
        .limit(1)
    ) is not None
    if has_transactions:
        raise HTTPException(
            status_code=409,
            detail="Esta posição tem operações no histórico. Registre uma venda para encerrar o saldo.",
        )
    _audit(db, current_user, client_id, "delete", item.id)
    db.delete(item)
    db.commit()
