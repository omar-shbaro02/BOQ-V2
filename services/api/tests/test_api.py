from app.config import get_settings
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_taxonomies_are_published() -> None:
    response = client.get("/api/v1/meta/taxonomies")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "1.1.0"
    assert payload["taxonomies"]["Disposition"] == [
        "NO_ACTION",
        "MONITOR",
        "VERIFY",
        "INTERVENE",
        "ESCALATE",
    ]


def test_local_identity_adapter_fails_closed_outside_development(monkeypatch) -> None:
    monkeypatch.setenv("VAI_ENVIRONMENT", "production")
    get_settings.cache_clear()
    try:
        response = client.get(
            "/api/v1/projects/11111111-1111-1111-1111-111111111111",
            headers={
                "X-VAI-Actor-ID": "forged@example.test",
                "X-VAI-Organization-ID": "11111111-1111-1111-1111-111111111111",
            },
        )
        assert response.status_code == 503
        assert (
            response.json()["detail"]
            == "OIDC identity adapter is required outside development/test"
        )
    finally:
        get_settings.cache_clear()
