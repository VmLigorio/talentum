from app.main import app


def test_client_access_routes_are_registered() -> None:
    routes = app.openapi()["paths"]

    assert {
        "/clients",
        "/clients/me/permissions",
        "/clients/{client_id}",
        "/clients/{client_id}/profile",
        "/clients/advisors",
        "/clients/{client_id}/assignment",
        "/clients/{client_id}/audit-log",
        "/clients/{client_id}/permissions",
        "/clients/{client_id}/action-plan",
        "/clients/{client_id}/investment-snapshots",
        "/clients/{client_id}/investment-snapshots/capture",
    }.issubset(routes)


def test_admin_user_management_routes_are_registered() -> None:
    routes = app.openapi()["paths"]

    assert {
        "/admin/users",
        "/admin/users/{user_id}/status",
        "/admin/users/{user_id}/reset-password",
    }.issubset(routes)
