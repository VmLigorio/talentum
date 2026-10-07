# Talentum — backend/app/api/investment_report.py
# Emite um relatório PDF detalhado da carteira atual do cliente.
from datetime import datetime, timezone
from decimal import Decimal
from html import escape
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.api.investment_positions import _find_client, _load_positions, _quote
from app.api.investment_monthly_performance import investment_monthly_performance
from app.db.database import get_db
from app.models import AuditLog, InvestmentTransaction, User
from app.services.authorization import require_client_manager
from app.services.market_data import MarketDataService


router = APIRouter(prefix="/clients", tags=["investment-reports"])
PAGE = landscape(A4)
INK = colors.HexColor("#18233A")
PURPLE = colors.HexColor("#5142A8")
MUTED = colors.HexColor("#64748B")
PALE = colors.HexColor("#F3F4F8")
GREEN = colors.HexColor("#087443")
RED = colors.HexColor("#B42318")


def _br(value: Decimal | float | int | None, places: int = 2) -> str:
    if value is None:
        return "—"
    number = f"{float(value):,.{places}f}"
    return number.replace(",", "_").replace(".", ",").replace("_", ".")


def _money(value: Decimal | float | int | None, currency: str | None) -> str:
    if value is None:
        return "Sem cotação"
    return f"{currency or 'BRL'} {_br(value)}"


def _safe(value: object | None) -> str:
    return escape(str(value)) if value not in (None, "") else "—"


def _paragraph(text: str, styles: dict[str, ParagraphStyle], style: str = "body") -> Paragraph:
    return Paragraph(text, styles[style])


def _table(rows: list[list[object]], widths: list[float], *, small: bool = False) -> Table:
    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), INK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7 if small else 8),
        ("LEADING", (0, 0), (-1, -1), 9 if small else 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#DCE1EA")),
    ]))
    return table


def _page(canvas, document) -> None:
    canvas.saveState()
    width, height = PAGE
    canvas.setStrokeColor(colors.HexColor("#DCE1EA"))
    canvas.line(14 * mm, 12 * mm, width - 14 * mm, 12 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawString(14 * mm, 7.5 * mm, "Talentum · Relatório informativo da carteira")
    canvas.drawRightString(width - 14 * mm, 7.5 * mm, f"Página {document.page}")
    canvas.restoreState()


def _position_market_details(service: MarketDataService, symbol: str, market: str) -> tuple[object | None, object | None]:
    try:
        details = service.details(symbol, market)  # type: ignore[arg-type]
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        details = None
    try:
        history = service.history(symbol, market, "1y")  # type: ignore[arg-type]
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        history = None
    return details, history


def _trailing_return(history: object | None) -> float | None:
    points = getattr(history, "points", []) or []
    if len(points) < 2 or not points[0].close:
        return None
    return ((points[-1].close / points[0].close) - 1) * 100


def _build_pdf(client: User, positions, service: MarketDataService, monthly, transactions) -> bytes:
    now = datetime.now(timezone.utc)
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=PAGE,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=15 * mm,
        bottomMargin=18 * mm,
        title=f"Relatório de investimentos — {client.name}",
        author="Talentum",
    )
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle("ReportTitle", parent=base["Title"], fontName="Helvetica-Bold", fontSize=21, leading=25, textColor=INK, alignment=TA_LEFT, spaceAfter=4),
        "subtitle": ParagraphStyle("ReportSubtitle", parent=base["Normal"], fontSize=9, leading=13, textColor=MUTED, spaceAfter=10),
        "section": ParagraphStyle("ReportSection", parent=base["Heading2"], fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=PURPLE, spaceBefore=12, spaceAfter=7),
        "subsection": ParagraphStyle("ReportSubsection", parent=base["Heading3"], fontName="Helvetica-Bold", fontSize=9, leading=12, textColor=INK, spaceBefore=5, spaceAfter=4),
        "body": ParagraphStyle("ReportBody", parent=base["BodyText"], fontSize=8.5, leading=12, textColor=INK, spaceAfter=4),
        "small": ParagraphStyle("ReportSmall", parent=base["BodyText"], fontSize=7.5, leading=10, textColor=MUTED, spaceAfter=3),
        "cell": ParagraphStyle("ReportCell", parent=base["BodyText"], fontSize=7, leading=9, textColor=INK),
        "right": ParagraphStyle("ReportRight", parent=base["BodyText"], fontSize=7, leading=9, textColor=INK, alignment=TA_RIGHT),
        "white": ParagraphStyle("ReportWhite", parent=base["BodyText"], fontName="Helvetica-Bold", fontSize=7, leading=9, textColor=colors.white),
    }
    story: list[object] = [
        _paragraph("Relatório detalhado da carteira", styles, "title"),
        _paragraph(f"Cliente: <b>{_safe(client.name)}</b> · Emitido em {now.astimezone().strftime('%d/%m/%Y às %H:%M %Z')} · Posições abertas na data de emissão", styles, "subtitle"),
        HRFlowable(width="100%", thickness=1.2, color=PURPLE),
        Spacer(1, 5 * mm),
    ]

    def collect(item):
        invested = item.quantity * item.average_price
        quote = _quote(item, service)
        _, current_price, currency, _ = quote
        currency = currency or ("BRL" if item.market == "br" else "USD")
        current_value = item.quantity * current_price if current_price is not None else None
        details, history = _position_market_details(service, item.symbol, item.market)
        return item, invested, current_value, currency, quote, details, history

    # Consultas de mercado independentes são executadas em paralelo para carteiras maiores.
    with ThreadPoolExecutor(max_workers=8) as pool:
        collected = list(pool.map(collect, positions))
    grouped: dict[str, list[tuple[object, Decimal, Decimal | None, str, object, object, object]]] = {}
    for record in collected:
        grouped.setdefault(record[3], []).append(record)

    story.append(_paragraph("Resumo executivo", styles, "section"))
    summary_rows = [[_paragraph("Moeda", styles, "white"), _paragraph("Custo registrado", styles, "white"), _paragraph("Custo cotado", styles, "white"), _paragraph("Valor de mercado", styles, "white"), _paragraph("Resultado não realizado", styles, "white"), _paragraph("Resultado %", styles, "white"), _paragraph("Posições", styles, "white")]]
    for currency, records in sorted(grouped.items()):
        invested = sum((record[1] for record in records), Decimal("0"))
        priced = [record for record in records if record[2] is not None]
        priced_cost = sum((record[1] for record in priced), Decimal("0"))
        current = sum((record[2] for record in priced if record[2] is not None), Decimal("0"))
        pnl = current - priced_cost
        percent = (pnl / priced_cost * 100) if priced and priced_cost else None
        summary_rows.append([currency, _money(invested, currency), _money(priced_cost, currency), _money(current, currency), _money(pnl, currency), f"{_br(percent)}%" if percent is not None else "—", str(len(records))])
    if len(summary_rows) == 1:
        summary_rows.append(["—", "Nenhuma posição cadastrada", "—", "—", "—", "—", "0"])
    story.append(_table(summary_rows, [20 * mm, 38 * mm, 38 * mm, 38 * mm, 42 * mm, 27 * mm, 18 * mm]))
    story.append(_paragraph("O custo cotado corresponde apenas às posições com cotação atual. Os totais são separados por moeda; ativos em moedas diferentes não são somados nem convertidos sem taxa de câmbio identificada.", styles, "small"))

    story.append(_paragraph("Desempenho no mês e comparação com o CDI", styles, "section"))
    story.append(_paragraph(f"Referência: {now.astimezone().strftime('%m/%Y')}. O desempenho mensal é estimado pelos registros de carteira disponíveis e comparado ao CDI diário publicado pelo Banco Central. O CDI e a comparação podem ficar indisponíveis quando a fonte externa ou a série histórica não responder.", styles, "body"))
    month_rows = [[_paragraph(value, styles, "white") for value in ["Moeda", "Investido no período", "Rendimento", "Retorno", "CDI", "Diferença vs. CDI", "% do CDI", "Cobertura"]]]
    for item in getattr(monthly, "currencies", []) or []:
        cdi_is_comparable = item.currency == "BRL"
        month_rows.append([
            item.currency,
            _money(item.invested_value, item.currency),
            _money(item.profit_value, item.currency),
            f"{_br(item.return_percent, 4)}%" if item.return_percent is not None else "—",
            f"{_br(item.cdi_percent, 4)}%" if cdi_is_comparable and item.cdi_percent is not None else ("Não aplicável" if not cdi_is_comparable else "—"),
            f"{_br(item.excess_percentage_points, 4)} p.p." if cdi_is_comparable and item.excess_percentage_points is not None else ("Não aplicável" if not cdi_is_comparable else "—"),
            f"{_br(item.percent_of_cdi, 2)}%" if cdi_is_comparable and item.percent_of_cdi is not None else ("Não aplicável" if not cdi_is_comparable else "—"),
            f"Desde {item.coverage_start.strftime('%d/%m/%Y')}" if item.coverage_start else "Sem histórico suficiente",
        ])
    if len(month_rows) == 1:
        month_rows.append(["—", "—", "—", "—", "—", "—", "—", "Dados mensais indisponíveis"])
    story.append(_table(month_rows, [18 * mm, 30 * mm, 30 * mm, 24 * mm, 20 * mm, 29 * mm, 22 * mm, 42 * mm], small=True))
    story.append(_paragraph("Uma carteira com snapshots parciais não representa necessariamente o mês completo. A comparação com o CDI é informativa e não considera diferenças de risco, tributação, taxas, liquidez ou aportes e retiradas ao longo do período.", styles, "small"))

    story.append(_paragraph("Detalhamento por ativo", styles, "section"))
    if not positions:
        story.append(_paragraph("Não há posições de investimento cadastradas para este cliente.", styles))
    for currency, records in sorted(grouped.items()):
        priced_total = sum((record[2] for record in records if record[2] is not None), Decimal("0"))
        story.append(_paragraph(f"{_safe(currency)} · {len(records)} posição(ões)", styles, "subsection"))
        rows = [[_paragraph(value, styles, "white") for value in ["Ativo", "Cotas", "Preço médio registrado", "Custo da posição", "Cotação atual", "Valor atual", "Variação", "Variação %", "Peso"]]]
        for item, invested, current_value, _, quote, _, _ in records:
            name, current_price, quote_currency, source = quote
            pnl = current_value - invested if current_value is not None else None
            pnl_percent = pnl / invested * 100 if pnl is not None and invested else None
            weight = current_value / priced_total * 100 if current_value is not None and priced_total else None
            asset_name = item.name or name or item.symbol
            rows.append([
                _paragraph(f"<b>{_safe(item.symbol)}</b><br/>{_safe(asset_name)}", styles, "cell"),
                _br(item.quantity, 8).rstrip("0").rstrip(","),
                _money(item.average_price, quote_currency),
                _money(invested, quote_currency),
                _money(current_price, quote_currency),
                _money(current_value, quote_currency),
                _money(pnl, quote_currency),
                f"{_br(pnl_percent)}%" if pnl_percent is not None else "—",
                f"{_br(weight)}%" if weight is not None else "—",
            ])
        story.append(_table(rows, [34 * mm, 20 * mm, 31 * mm, 31 * mm, 30 * mm, 31 * mm, 30 * mm, 23 * mm, 18 * mm], small=True))
        story.append(Spacer(1, 3 * mm))

        for item, invested, current_value, _, quote, details, history in records:
            _, current_price, currency_name, source = quote
            pnl = current_value - invested if current_value is not None else None
            pnl_percent = pnl / invested * 100 if pnl is not None and invested else None
            paragraphs = [
                _paragraph(f"{_safe(item.symbol)} · ficha complementar", styles, "subsection"),
                _paragraph(
                    f"Mercado: {_safe('B3 / Brasil' if item.market == 'br' else 'Exterior')} · Moeda: {_safe(currency_name)} · Classe: {_safe(getattr(details, 'asset_type', None))} · Bolsa: {_safe(getattr(details, 'exchange', None))}<br/>"
                    f"Setor: {_safe(getattr(details, 'sector', None))} · Subsetor: {_safe(getattr(details, 'subsector', None))} · Indústria: {_safe(getattr(details, 'industry', None))}<br/>"
                    f"Variação diária do ativo: {_br(getattr(details, 'change', None))} ({_br(getattr(details, 'change_percent', None))}%) · Fechamento anterior: {_br(getattr(details, 'previous_close', None))}<br/>"
                    f"Faixa de 52 semanas: {_br(getattr(details, 'fifty_two_week_low', None))} a {_br(getattr(details, 'fifty_two_week_high', None))} · Dividend yield informado: {_br(getattr(details, 'dividend_yield', None), 4)}% · P/L: {_br(getattr(details, 'price_earnings', None), 2)} · P/VP: {_br(getattr(details, 'price_to_book', None), 2)}<br/>"
                    f"Retorno observado em 12 meses: {_br(_trailing_return(history), 2)}% · Volatilidade anualizada: {_br(getattr(history, 'annualized_volatility', None), 2)}% · Máxima queda observada no período: {_br(getattr(history, 'max_drawdown', None), 2)}%<br/>"
                    f"Fonte da cotação: {_safe(source or getattr(details, 'source', None))} · Cotação atual: {_money(current_price, currency_name)} · Variação não realizada desta posição: {_money(pnl, currency_name)} ({_br(pnl_percent)}%)",
                    styles,
                ),
            ]
            if getattr(details, "fii_report", None):
                fii = details.fii_report
                paragraphs.append(_paragraph(
                    f"Dados do relatório imobiliário disponível: patrimônio líquido {_money(fii.equity, currency_name)}, valor patrimonial por cota {_money(fii.nav_per_share, currency_name)}, retorno mensal {_br(fii.monthly_return, 2)}%, dividend yield mensal {_br(fii.monthly_dividend_yield, 2)}%, data de referência {_safe(fii.reference_date)}.",
                    styles, "small",
                ))
            if item.institution:
                paragraphs.append(_paragraph(f"Instituição informada: {_safe(item.institution)}", styles, "small"))
            if item.notes:
                paragraphs.append(_paragraph(f"Observações registradas: {_safe(item.notes)}", styles, "small"))
            as_of = getattr(details, "as_of_date", None) or getattr(details, "updated_at", None)
            paragraphs.append(_paragraph(f"Data informada pela fonte: {_safe(as_of)} · Cadastro da posição: {item.created_at.astimezone().strftime('%d/%m/%Y') if item.created_at else '—'} · Última alteração no cadastro: {item.updated_at.astimezone().strftime('%d/%m/%Y') if item.updated_at else '—'}. A data do cadastro não comprova a data de aquisição.", styles, "small"))
            story.append(KeepTogether(paragraphs))
            story.append(Spacer(1, 2 * mm))

    story.append(_paragraph("Histórico de operações registradas", styles, "section"))
    if transactions:
        operation_rows = [[_paragraph(value, styles, "white") for value in ["Data", "Operação", "Ativo", "Cotas", "Preço unitário", "Valor bruto", "Taxas", "Valor líquido", "Resultado realizado"]]]
        for item in transactions:
            operation_rows.append([
                item.operation_date.strftime("%d/%m/%Y"),
                ("Compra" if item.operation_type == "buy" else "Venda") + (" anulada" if item.voided_at else ""),
                _paragraph(
                    f"<b>{_safe(item.symbol)}</b><br/>{_safe(item.name)}"
                    + (f"<br/>Anulação: {_safe(item.void_reason)}" if item.voided_at else ""),
                    styles,
                    "cell",
                ),
                _br(item.quantity, 8).rstrip("0").rstrip(","),
                _money(item.unit_price, item.currency),
                _money(item.gross_value, item.currency),
                _money(item.fees, item.currency),
                _money(item.net_value, item.currency),
                _money(item.realized_pnl, item.currency) if item.realized_pnl is not None and item.voided_at is None else "—",
            ])
        story.append(_table(operation_rows, [22 * mm, 20 * mm, 28 * mm, 19 * mm, 28 * mm, 28 * mm, 22 * mm, 28 * mm, 34 * mm], small=True))
        story.append(_paragraph("O histórico exibe as até 300 operações mais recentes. A posição de abertura pode conter saldo anterior ao início dos registros; o preço médio anterior e posterior de cada lançamento ficam guardados para rastreabilidade.", styles, "small"))
    else:
        story.append(_paragraph("Ainda não há compras ou vendas registradas. Os saldos cadastrados antes do início do histórico são considerados posições de abertura e não têm operações anteriores detalhadas.", styles))

    story.append(_paragraph("Critérios, cobertura e limitações", styles, "section"))
    caveats = [
        "O custo da posição é calculado pela quantidade atual multiplicada pelo preço médio registrado no Talentum. O sistema não mantém, neste momento, o livro de ordens com preço, data, quantidade e taxas de cada compra ou venda; portanto, o relatório não atribui um preço histórico individual a cada aquisição.",
        "A variação por ativo compara o custo médio registrado com a cotação consultada na emissão. É uma estimativa não realizada das posições atuais; não inclui impostos, taxas, proventos, amortizações, câmbio ou posições encerradas, salvo quando esses dados são mantidos no cadastro do ativo.",
        "Cotações, indicadores e histórico podem ter horários de atualização diferentes, atraso de mercado ou indisponibilidade do provedor. Campos sem fonte ou sem histórico suficiente são exibidos como indisponíveis e não como zero.",
        "A alocação percentual é calculada dentro de cada moeda, sem conversão cambial. Ativos com cotação indisponível ficam fora do denominador do peso e são mantidos na contagem de posições.",
        "Este documento é informativo, representa os dados disponíveis na data de emissão e não constitui recomendação de investimento, promessa de rentabilidade ou garantia de resultados futuros.",
    ]
    for caveat in caveats:
        story.append(_paragraph(f"• {escape(caveat)}", styles, "small"))

    document.build(story, onFirstPage=_page, onLaterPages=_page)
    return buffer.getvalue()


@router.get("/{client_id}/investment-report.pdf")
def download_investment_report(
    client_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    client = _find_client(client_id, db)
    require_client_manager(client_id, current_user, db)
    positions = _load_positions(client_id, db)
    transactions = list(
        db.scalars(
            select(InvestmentTransaction)
            .where(InvestmentTransaction.client_id == client_id)
            .order_by(
                InvestmentTransaction.operation_date.desc(),
                InvestmentTransaction.id.desc(),
            )
            .limit(300)
        ).all()
    )
    service = MarketDataService()
    try:
        monthly = investment_monthly_performance(client_id, current_user, db)
    except (HTTPException, httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError):
        monthly = None
    try:
        content = _build_pdf(client, positions, service, monthly, transactions)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Não foi possível montar o relatório da carteira agora.") from exc
    db.add(AuditLog(
        actor_user_id=current_user.id,
        client_user_id=client_id,
        action="export",
        resource="investment_report",
            details={"position_count": len(positions), "transaction_count": len(transactions), "format": "pdf"},
    ))
    db.commit()
    filename = f"relatorio-carteira-talentum-{client_id}.pdf"
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
