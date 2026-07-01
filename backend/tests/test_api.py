from fastapi.testclient import TestClient

from app.main import app, database


def test_health_reports_degraded_when_database_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(database, "ping", lambda: False)
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"


def test_expected_api_surface_is_documented() -> None:
    paths = app.openapi()["paths"]
    assert {
        "/health",
        "/chat",
        "/admin/ingest",
        "/evaluations/run",
        "/evaluations/latest",
        "/metrics/summary",
    } <= set(paths)
