import httpx
import pytest
from app.config import get_settings
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_default_profile_rejects_external_http_before_network_access() -> None:
    with pytest.raises(AssertionError, match="External HTTP is disabled"):
        httpx.get("https://example.invalid")


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_taxonomies_are_published() -> None:
    response = client.get("/api/v1/meta/taxonomies")
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "1.10.0"
    assert payload["taxonomies"]["Disposition"] == [
        "NO_ACTION",
        "MONITOR",
        "VERIFY",
        "INTERVENE",
        "ESCALATE",
    ]
    assert payload["taxonomies"]["BoqExtractionStatus"] == [
        "RECEIVED",
        "EXTRACTED",
        "VERIFICATION_REQUIRED",
        "FAILED",
    ]
    assert payload["taxonomies"]["ProgressWeightingBasis"] == [
        "BOQ_VALUE",
        "COST_VALUE",
        "QUANTITY",
        "MANUAL_AUTHORIZED",
    ]


def test_default_test_settings_do_not_use_external_ai_credentials() -> None:
    settings = get_settings()
    assert settings.environment == "test"
    assert settings.openai_agents_enabled is False
    assert not settings.openai_api_key


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
            == "OIDC identity adapter requires issuer, audience, and JWKS URL"
        )
    finally:
        get_settings.cache_clear()
