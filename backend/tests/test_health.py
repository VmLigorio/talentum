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
