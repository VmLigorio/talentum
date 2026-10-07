# Talentum — backend/tests/test_auth_routes.py
# Responsabilidade: Contém testes automatizados que protegem o comportamento esperado do sistema.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from app.main import app


def test_auth_routes_are_registered() -> None:
    routes = app.openapi()["paths"]

    assert {"/auth/login", "/auth/refresh", "/auth/logout", "/auth/change-password", "/auth/me"}.issubset(
        routes
    )


def test_openapi_authorization_accepts_a_bearer_token() -> None:
    security_schemes = app.openapi()["components"]["securitySchemes"]

    assert security_schemes["HTTPBearer"]["type"] == "http"
    assert security_schemes["HTTPBearer"]["scheme"] == "bearer"


def test_admin_routes_are_registered() -> None:
    assert {"/admin/users", "/admin/users/{user_id}/status"}.issubset(
        app.openapi()["paths"]
    )
