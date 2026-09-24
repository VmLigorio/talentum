# Talentum — backend/tests/test_health.py
# Responsabilidade: Contém testes automatizados que protegem o comportamento esperado do sistema.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from app.main import app, health_check


def test_health_check() -> None:
    assert health_check() == {
        "status": "ok",
        "service": "talentum-api",
    }


def test_health_route_is_registered() -> None:
    routes = app.openapi()["paths"]

    assert "/health" in routes
    assert "/health/ready" in routes
