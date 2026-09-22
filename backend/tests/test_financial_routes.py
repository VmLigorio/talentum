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
