import asyncio
import logging
import re
from time import perf_counter
from uuid import uuid4
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

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
from app.core.config import get_cors_origins, get_settings, get_trusted_hosts
from app.db.database import SessionLocal, get_db
from app.services.market_alerts import sync_all_market_alerts
from app.services.notifications import sync_document_review_notifications
from app.services.portfolio_snapshots import capture_all_portfolio_snapshots
from app.models import User


logger = logging.getLogger(__name__)
settings = get_settings()


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
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


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")
        if content_length and content_length.isdigit() and int(content_length) > settings.max_request_body_bytes:
            return Response("Requisição excede o limite permitido", status_code=413)
        return await call_next(request)


class RequestObservabilityMiddleware(BaseHTTPMiddleware):
    """Adds a safe correlation id and duration without logging sensitive payloads."""

    _request_id_pattern = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

    @classmethod
    def _request_id(cls, request: Request) -> str:
        candidate = request.headers.get("X-Request-ID", "")
        return candidate if cls._request_id_pattern.fullmatch(candidate) else uuid4().hex

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = self._request_id(request)
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
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


def _run_market_alert_sync() -> tuple[int, int]:
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


async def market_alert_monitor() -> None:
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


def _run_portfolio_snapshot_capture() -> tuple[int, int, int]:
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


async def portfolio_snapshot_monitor() -> None:
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


def _run_document_review_sync() -> int:
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


async def document_review_monitor() -> None:
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
async def lifespan(_: FastAPI):
    monitor_task = asyncio.create_task(market_alert_monitor())
    snapshot_task = asyncio.create_task(portfolio_snapshot_monitor())
    document_review_task = asyncio.create_task(document_review_monitor())
    try:
        yield
    finally:
        monitor_task.cancel()
        snapshot_task.cancel()
        document_review_task.cancel()
        await asyncio.gather(
            monitor_task,
            snapshot_task,
            document_review_task,
            return_exceptions=True,
        )


app = FastAPI(
    title="Talentum API",
    description="API da plataforma de organização e acompanhamento patrimonial.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.api_docs_enabled else None,
    redoc_url="/redoc" if settings.api_docs_enabled else None,
    openapi_url="/openapi.json" if settings.api_docs_enabled else None,
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(RequestObservabilityMiddleware)
if settings.environment.strip().lower() in {"production", "prod"}:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=get_trusted_hosts())

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


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Return the minimum liveness response for local and future deploy checks."""

    return {
        "status": "ok",
        "service": "talentum-api",
    }


@app.get("/health/ready", tags=["system"])
def readiness_check(db=Depends(get_db)) -> dict[str, str]:
    """Verify that the API process and its database are ready for requests."""

    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Banco de dados indisponível") from exc
    return {
        "status": "ready",
        "service": "talentum-api",
        "database": "ok",
    }
