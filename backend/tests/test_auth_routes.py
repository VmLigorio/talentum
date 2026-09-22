from app.main import app


def test_auth_routes_are_registered() -> None:
    routes = app.openapi()["paths"]

    assert {"/auth/login", "/auth/refresh", "/auth/logout", "/auth/change-password", "/auth/me"}.issubset(
        routes
    )


def test_admin_routes_are_registered() -> None:
    assert {"/admin/users", "/admin/users/{user_id}/status"}.issubset(
        app.openapi()["paths"]
    )
