# Talentum — backend/tests/test_health.py
# Responsabilidade: Contém testes automatizados que protegem o comportamento esperado do sistema.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from app.main import app, health_check


def test_health_check() -> None:
    """Verifica a resposta mínima do endpoint de disponibilidade."""
    assert health_check() == {
        "status": "ok",
        "service": "talentum-api",
    }


def test_health_route_is_registered() -> None:
    """Verifica o registro do endpoint de saúde na aplicação."""
    routes = app.openapi()["paths"]

    assert "/health" in routes
    assert "/health/ready" in routes
