# Talentum — backend/tests/test_financial_routes.py
# Responsabilidade: Contém testes automatizados que protegem o comportamento esperado do sistema.
# Os blocos abaixo estão organizados por responsabilidade para facilitar a manutenção.
from app.main import app


def test_financial_routes_are_registered() -> None:
    routes = app.openapi()["paths"]

    assert {
        "/clients/{client_id}/financial-profile",
        "/clients/{client_id}/patrimony",
        "/clients/{client_id}/patrimony/{item_id}",
        "/clients/{client_id}/goals",
        "/clients/{client_id}/goals/{goal_id}",
    }.issubset(routes)
