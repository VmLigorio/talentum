from app.main import app


def test_dashboard_and_report_routes_are_registered() -> None:
    routes = app.openapi()["paths"]

    assert {
        "/clients/{client_id}/dashboard",
        "/clients/{client_id}/reports",
        "/clients/{client_id}/reports/{report_id}",
        "/clients/{client_id}/documents",
        "/clients/{client_id}/documents/{document_id}/download",
    }.issubset(routes)
    assert {
        "/notifications",
        "/notifications/unread-count",
        "/notifications/{notification_id}/read",
        "/notifications/read-all",
        "/notifications/preferences",
        "/market/search",
        "/market/alerts",
        "/market/alerts/{alert_id}",
        "/market/watchlist",
        "/market/watchlist/{item_id}",
        "/clients/{client_id}/investment-portfolio",
        "/clients/{client_id}/investment-positions",
        "/clients/{client_id}/investment-positions/{position_id}",
        "/clients/{client_id}/investment-analytics",
    }.issubset(routes)
    assert "delete" in routes["/clients/{client_id}/reports/{report_id}"]
