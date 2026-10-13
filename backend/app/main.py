"""Inicializa a API, seus middlewares, rotas e tarefas de fundo."""

import asyncio
import logging
import re
import socket
from time import perf_counter
from uuid import uuid4
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from redis import Redis
from redis.exceptions import RedisError

from app.api.auth import router as auth_router
from app.api.admin import router as admin_router
from app.api.clients import router as clients_router
from app.api.financial import router as financial_router
from app.api.dashboard import router as dashboard_router
from app.api.reports import router as reports_router
from app.api.actions import router as actions_router
from app.api.documents import router as documents_router
from app.api.notifications import router as notifications_router
from app.api.notification_preferences import router as notification_preferences_router
from app.api.market import router as market_router
from app.api.market_alerts import router as market_alerts_router
from app.api.market_watchlist import router as market_watchlist_router
from app.api.investment_positions import router as investment_positions_router
from app.api.investment_analytics import router as investment_analytics_router
from app.api.portfolio_snapshots import router as portfolio_snapshots_router
from app.api.investment_monthly_performance import router as investment_monthly_performance_router
from app.api.investment_report import router as investment_report_router
from app.api.investment_transactions import router as investment_transactions_router
from app.api.suitability import router as suitability_router
from app.core.config import get_cors_origins, get_settings, get_trusted_hosts
from app.db.database import SessionLocal, get_db
from app.services.market_alerts import sync_all_market_alerts
from app.services.notifications import sync_document_review_notifications
from app.services.portfolio_snapshots import capture_all_portfolio_snapshots
from app.models import User


logger = logging.getLogger(__name__)
settings = get_settings()


# Adiciona cabeçalhos básicos para reduzir riscos no navegador e em proxies.
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Acrescenta cabeçalhos de segurança às respostas HTTP."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Aplica os cabeçalhos padrão e regras adicionais de produção."""
        response = await call_next(request)
        # Erros não tratados saem daqui; o 500 é montado pelo middleware externo (achado 164).
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault("Cross-Origin-Resource-Policy", "cross-origin")
        if request.url.path.startswith("/auth"):
            response.headers.setdefault("Cache-Control", "no-store")
        if settings.environment.strip().lower() in {"production", "prod"}:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


# Rejeita antecipadamente requisições cujo Content-Length declarado excede o limite.
class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Rejeita requisições cujo tamanho declarado excede o limite configurado."""

    async def dispatch(self, request: Request, call_next) -> Response:
        """Verifica Content-Length antes de encaminhar a requisição."""
        content_length = request.headers.get("content-length")
        if content_length and content_length.isdigit() and int(content_length) > settings.max_request_body_bytes:
            return Response("Requisição excede o limite permitido", status_code=413)
        return await call_next(request)


# Mede cada requisição e registra um identificador útil para diagnóstico.
class RequestObservabilityMiddleware(BaseHTTPMiddleware):
    """Registra duração e identificador de correlação sem gravar o payload."""

    _request_id_pattern = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

    @classmethod
    def _request_id(cls, request: Request) -> str:
        """Reutiliza um identificador válido ou cria um identificador novo."""
        candidate = request.headers.get("X-Request-ID", "")
        return candidate if cls._request_id_pattern.fullmatch(candidate) else uuid4().hex

    async def dispatch(self, request: Request, call_next) -> Response:
        """Mede a requisição, adiciona cabeçalhos e registra o resultado."""
        request_id = self._request_id(request)
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            # Tracebacks de falhas SQL podem incluir parâmetros; ver achado 163 antes de ampliar este log.
            logger.exception(
                "Falha não tratada na requisição %s %s (request_id=%s)",
                request.method,
                request.url.path,
                request_id,
            )
            raise
        duration_ms = (perf_counter() - started) * 1000
        response.headers.setdefault("X-Request-ID", request_id)
        response.headers.setdefault("X-Response-Time-ms", f"{duration_ms:.2f}")
        logger.info(
            "Requisição %s %s respondeu %s em %.2f ms (request_id=%s)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        return response


# Executa a verificação de alertas em modo síncrono dentro do ciclo assíncrono.
def _run_market_alert_sync() -> tuple[int, int]:
    """Executa a sincronização de alertas com sessão de banco própria."""
    db = SessionLocal()
    try:
        checked, triggered, changed = sync_all_market_alerts(db)
        if changed:
            db.commit()
        return checked, triggered
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# Tarefa periódica que converte cotações atingidas em notificações.
async def market_alert_monitor() -> None:
    """Verifica periodicamente cotações e dispara alertas de mercado."""
    interval = max(30, get_settings().market_alert_check_interval_seconds)
    while True:
        try:
            checked, triggered = await asyncio.to_thread(_run_market_alert_sync)
            if checked or triggered:
                logger.info("Verificação de alertas de mercado: %s cotações consultadas, %s alertas disparados", checked, triggered)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Falha na verificação automática de alertas de mercado")
        await asyncio.sleep(interval)


# Captura o valor da carteira de clientes com posições atualizadas.
def _run_portfolio_snapshot_capture() -> tuple[int, int, int]:
    """Captura snapshots usando uma sessão isolada do banco de dados."""
    db = SessionLocal()
    try:
        clients_checked, snapshots_created, failures = capture_all_portfolio_snapshots(db)
        if snapshots_created:
            db.commit()
        return clients_checked, snapshots_created, failures
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# Tarefa periódica que preserva a evolução histórica das carteiras.
async def portfolio_snapshot_monitor() -> None:
    """Agenda a captura periódica do histórico de valores das carteiras."""
    interval = max(300, get_settings().portfolio_snapshot_interval_seconds)
    while True:
        try:
            clients_checked, snapshots_created, failures = await asyncio.to_thread(_run_portfolio_snapshot_capture)
            if clients_checked or snapshots_created or failures:
                logger.info(
                    "Snapshot da carteira: %s clientes, %s registros criados, %s falhas",
                    clients_checked,
                    snapshots_created,
                    failures,
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Falha na captura automática de snapshots da carteira")
        await asyncio.sleep(interval)


# Cria avisos para documentos cujo ciclo anual de revisão venceu.
def _run_document_review_sync() -> int:
    """Atualiza avisos de revisão documental para clientes ativos."""
    db = SessionLocal()
    try:
        client_ids = list(
            db.scalars(
                select(User.id).where(
                    User.role == "client",
                    User.is_active.is_(True),
                )
            ).all()
        )
        changed_clients = 0
        for client_id in client_ids:
            if sync_document_review_notifications(client_id, db):
                changed_clients += 1
        if changed_clients:
            db.commit()
        return changed_clients
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# Tarefa periódica de conformidade documental.
async def document_review_monitor() -> None:
    """Agenda diariamente a verificação dos prazos de documentos."""
    interval = 24 * 60 * 60
    while True:
        try:
            changed_clients = await asyncio.to_thread(_run_document_review_sync)
            if changed_clients:
                logger.info(
                    "Verificação anual de documentos: %s clientes com aviso atualizado",
                    changed_clients,
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Falha na verificação anual de documentos")
        await asyncio.sleep(interval)


@asynccontextmanager
# Inicia e encerra as tarefas periódicas junto com o processo FastAPI.
async def lifespan(_: FastAPI):
    """Inicia os monitores e cancela suas corrotinas ao encerrar a API."""
    # Cada processo da API inicia uma cópia dos monitores; o Compose de produção usa uma instância.
    monitor_task = asyncio.create_task(market_alert_monitor())
    snapshot_task = asyncio.create_task(portfolio_snapshot_monitor())
    document_review_task = asyncio.create_task(document_review_monitor())
    logger.info(
        "Monitores iniciados: alertas a cada %ss, snapshots a cada %ss, revisão documental a cada 24h; mantenha uma instância da API",
        max(30, get_settings().market_alert_check_interval_seconds),
        max(300, get_settings().portfolio_snapshot_interval_seconds),
    )
    try:
        yield
    finally:
        # O cancelamento da corrotina não interrompe uma função já em execução por asyncio.to_thread.
        monitor_task.cancel()
        snapshot_task.cancel()
        document_review_task.cancel()
        # Aguarda as corrotinas monitoras; a função de thread pode continuar até terminar.
        await asyncio.gather(
            monitor_task,
            snapshot_task,
            document_review_task,
            return_exceptions=True,
        )
        logger.info("Monitores da API encerrados")


app = FastAPI(
    title="Talentum API",
    description="API da plataforma de organização e acompanhamento patrimonial.",
    version="0.1.0",
    lifespan=lifespan,
    # Estes endpoints OpenAPI não têm autenticação; a implantação precisa defini-los como desativados.
    docs_url="/docs" if settings.api_docs_enabled else None,
    redoc_url="/redoc" if settings.api_docs_enabled else None,
    openapi_url="/openapi.json" if settings.api_docs_enabled else None,
)

# Middlewares transversais são registrados antes das rotas.
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(RequestObservabilityMiddleware)
if settings.environment.strip().lower() in {"production", "prod"}:
    # O host usado pelo healthcheck local também precisa constar na lista configurada.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=get_trusted_hosts())

# CORS libera origens, métodos e cabeçalhos de entrada; cabeçalhos de resposta
# personalizados, como os de observabilidade, precisam ser expostos separadamente.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(clients_router)
app.include_router(financial_router)
app.include_router(dashboard_router)
app.include_router(reports_router)
app.include_router(actions_router)
app.include_router(documents_router)
app.include_router(notifications_router)
app.include_router(notification_preferences_router)
app.include_router(market_router)
app.include_router(market_alerts_router)
app.include_router(market_watchlist_router)
app.include_router(investment_positions_router)
app.include_router(investment_analytics_router)
app.include_router(portfolio_snapshots_router)
app.include_router(investment_monthly_performance_router)
app.include_router(investment_report_router)
app.include_router(investment_transactions_router)
app.include_router(suitability_router)


# Verificação simples para confirmar que o processo da API está ativo.
@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Confirma que o processo da API está respondendo."""

    return {
        "status": "ok",
        "service": "talentum-api",
    }


@app.get("/health/ready", tags=["system"])
def readiness_check(db=Depends(get_db)) -> dict[str, str]:
    """Confirma o banco e os serviços configurados como obrigatórios."""
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Banco de dados indisponível") from exc
    dependency_status = {"database": "ok", "redis": "not_required", "clamav": "not_required"}
    if settings.redis_required:
        try:
            with Redis.from_url(
                settings.redis_url,
                socket_connect_timeout=2,
                socket_timeout=2,
            ) as redis_client:
                if not redis_client.ping():
                    raise RedisError("Redis não confirmou a operação PING")
        except (RedisError, ValueError) as exc:
            raise HTTPException(status_code=503, detail="Serviço obrigatório indisponível") from exc
        dependency_status["redis"] = "ok"
    if settings.clamav_required:
        try:
            with socket.create_connection((settings.clamav_host, settings.clamav_port), timeout=2) as client:
                client.settimeout(2)
                client.sendall(b"zPING\0")
                if client.recv(64).rstrip(b"\0") != b"PONG":
                    raise OSError("Resposta inesperada do serviço antivírus")
        except OSError as exc:
            raise HTTPException(status_code=503, detail="Serviço obrigatório indisponível") from exc
        dependency_status["clamav"] = "ok"
    return {
        "status": "ready",
        "service": "talentum-api",
        **dependency_status,
    }
