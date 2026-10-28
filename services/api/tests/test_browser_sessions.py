import base64
import hashlib
import json
import time
import uuid
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlsplit

import httpx
import jwt
import pytest
from app.config import get_settings
from app.main import app
from app.web_sessions import LOGIN_COOKIE, SESSION_COOKIE, seal, session_cipher, unseal
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient


@pytest.fixture
def browser_login(monkeypatch):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    organization = str(uuid.uuid4())
    values = {
        "VAI_ENVIRONMENT": "production",
        "VAI_OIDC_ISSUER": "https://login.example/",
        "VAI_OIDC_AUDIENCE": "vai-api",
        "VAI_OIDC_JWKS_URL": "https://login.example/keys",
        "VAI_OIDC_CLIENT_ID": "browser-client",
        "VAI_OIDC_CLIENT_SECRET": "test-client-secret",
        "VAI_OIDC_AUTHORIZATION_URL": "https://login.example/authorize",
        "VAI_OIDC_TOKEN_URL": "https://login.example/oauth/token",
        "VAI_SESSION_PUBLIC_ORIGIN": "https://app.example",
        "VAI_SESSION_ENCRYPTION_KEYS": json.dumps([Fernet.generate_key().decode()]),
        "VAI_RATE_LIMIT_PER_MINUTE": "10000",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    keys = SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=private.public_key())
    )
    monkeypatch.setattr("app.oidc.signing_keys", lambda *args: keys)
    monkeypatch.setattr("app.routers.authentication.signing_keys", lambda *args: keys)
    client = TestClient(app, base_url="https://app.example", follow_redirects=False)
    now = int(time.time())
    access_claims = {
        "iss": values["VAI_OIDC_ISSUER"],
        "aud": "vai-api",
        "sub": "auth0|operator",
        "iat": now - 1,
        "exp": now + 1200,
        "https://vai.example/organization_id": organization,
    }
    access_token = jwt.encode(access_claims, private, algorithm="RS256", headers={"kid": "key-1"})
    captured = []
    id_changes = {}
    token_changes = {}
    failures = {}
    original_client = httpx.AsyncClient

    def token_response(request):
        captured.append(request)
        if failures.get("status"):
            return httpx.Response(failures["status"], json={"error": "secret-provider-error"})
        transaction = unseal(get_settings(), client.cookies.get(LOGIN_COOKIE), 600)
        identity = {
            "iss": values["VAI_OIDC_ISSUER"],
            "aud": "browser-client",
            "sub": "auth0|operator",
            "iat": now - 1,
            "exp": now + 1200,
            "nonce": transaction["nonce"],
            **id_changes,
        }
        id_token = jwt.encode(identity, private, algorithm="RS256", headers={"kid": "key-1"})
        return httpx.Response(
            200,
            json={
                "access_token": access_token,
                "id_token": id_token,
                "expires_in": 1200,
                "token_type": "Bearer",
                **token_changes,
            },
        )

    monkeypatch.setattr(
        "app.routers.authentication.httpx.AsyncClient",
        lambda **kwargs: original_client(**kwargs, transport=httpx.MockTransport(token_response)),
    )
    try:
        yield SimpleNamespace(
            client=client,
            captured=captured,
            id_changes=id_changes,
            token_changes=token_changes,
            failures=failures,
            access_token=access_token,
            organization=organization,
            machine_token=jwt.encode(
                {
                    **access_claims,
                    "gty": "client-credentials",
                    "https://vai.example/principal_type": "HUMAN",
                },
                private,
                algorithm="RS256",
                headers={"kid": "key-1"},
            ),
        )
    finally:
        client.close()


def begin(fixture):
    response = fixture.client.get("/api/v1/auth/login")
    assert response.status_code == 303, response.text
    query = parse_qs(urlsplit(response.headers["location"]).query)
    return response, query


def callback(fixture, state):
    return fixture.client.get(
        "/api/v1/auth/callback?" + urlencode({"code": "one-use-code", "state": state})
    )


def test_browser_login_pkce_identity_cookie_and_logout(browser_login):
    fixture = browser_login
    start, query = begin(fixture)
    assert query["response_type"] == ["code"] and query["code_challenge_method"] == ["S256"]
    assert query["redirect_uri"] == ["https://app.example/api/v1/auth/callback"]
    transaction = unseal(get_settings(), fixture.client.cookies.get(LOGIN_COOKIE), 600)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(transaction["verifier"].encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    assert query["code_challenge"] == [challenge]
    assert transaction["verifier"] not in start.headers["location"]
    result = callback(fixture, query["state"][0])
    assert result.status_code == 303, result.text
    assert result.headers["location"] == "https://app.example/"
    body = parse_qs(fixture.captured[0].content.decode())
    assert body["code_verifier"] == [transaction["verifier"]]
    assert body["client_secret"] == ["test-client-secret"]
    assert body["redirect_uri"] == query["redirect_uri"]
    cookie = fixture.client.cookies.get(SESSION_COOKIE)
    assert fixture.access_token not in cookie
    header = result.headers.get_list("set-cookie")[0]
    for flag in ("HttpOnly", "Secure", "SameSite=lax", "Path=/"):
        assert flag in header
    assert "Domain=" not in header
    session = fixture.client.get(
        "/api/v1/auth/session",
        headers={"X-VAI-Actor-ID": "forged", "X-VAI-Roles": "ORGANIZATION_ADMIN"},
    )
    assert session.json() == {
        "mode": "OIDC",
        "actor_id": "auth0|operator",
        "organization_id": fixture.organization,
    }
    assert fixture.access_token not in session.text and "test-client-secret" not in session.text
    for origin in (None, "https://evil.example", "null"):
        denied = fixture.client.post(
            "/api/v1/auth/logout", headers={"Origin": origin} if origin else {}
        )
        assert denied.status_code == 403
    logged_out = fixture.client.post(
        "/api/v1/auth/logout", headers={"Origin": "https://app.example"}
    )
    assert logged_out.status_code == 204
    assert fixture.client.get("/api/v1/auth/session").status_code == 401


def test_login_state_missing_expired_and_tampered_fail_before_exchange(browser_login):
    fixture = browser_login
    _, query = begin(fixture)
    assert callback(fixture, "wrong-state").status_code == 401
    assert callback(fixture, "wrong-\u00e9-state").status_code == 401
    assert not fixture.captured
    original = fixture.client.cookies.get(LOGIN_COOKIE)
    settings = get_settings()
    transaction = unseal(settings, original, 600)
    old = (
        session_cipher(settings)
        ._fernets[0]
        .encrypt_at_time(json.dumps(transaction).encode(), int(time.time()) - 601)
        .decode()
    )
    for value in (old, "tampered", seal(settings, {"kind": "login", "state": query["state"][0]})):
        fixture.client.cookies.clear()
        fixture.client.cookies.set(LOGIN_COOKIE, value, domain="app.example", path="/")
        assert callback(fixture, query["state"][0]).status_code == 401
    fixture.client.cookies.clear()
    assert callback(fixture, query["state"][0]).status_code == 401
    assert not fixture.captured


@pytest.mark.parametrize(
    "changes",
    [
        {"nonce": "wrong"},
        {"sub": "other-subject"},
        {"aud": "other-client"},
        {"exp": 1},
        {"azp": "wrong-client"},
        {"at_hash": "wrong-binding"},
        {"aud": ["browser-client", "other-client"]},
    ],
)
def test_login_identity_binding_denials(browser_login, changes):
    fixture = browser_login
    fixture.id_changes.update(changes)
    _, query = begin(fixture)
    denied = callback(fixture, query["state"][0])
    assert denied.status_code == 401, denied.text
    assert fixture.client.cookies.get(SESSION_COOKIE) is None


@pytest.mark.parametrize(
    "changes",
    [
        {"access_token": "invalid"},
        {"token_type": "unknown"},
        {"expires_in": -1},
        {"expires_in": "1200"},
        {"expires_in": True},
        {"id_token": None},
        {"token_type": 1},
        {"access_token": None},
    ],
)
def test_invalid_token_result_cannot_create_browser_session(browser_login, changes):
    fixture = browser_login
    fixture.token_changes.update(changes)
    _, query = begin(fixture)
    denied = callback(fixture, query["state"][0])
    assert denied.status_code == 401, denied.text
    assert fixture.client.cookies.get(SESSION_COOKIE) is None


def test_token_exchange_outage_is_sanitized_and_session_key_rotation(browser_login, monkeypatch):
    fixture = browser_login
    fixture.failures["status"] = 500
    _, query = begin(fixture)
    outage = callback(fixture, query["state"][0])
    assert outage.status_code == 503 and "secret-provider-error" not in outage.text
    settings = get_settings()
    previous = settings.session_encryption_keys[0].get_secret_value()
    sealed = seal(settings, {"kind": "test"})
    monkeypatch.setenv(
        "VAI_SESSION_ENCRYPTION_KEYS", json.dumps([Fernet.generate_key().decode(), previous])
    )
    get_settings.cache_clear()
    assert unseal(get_settings(), sealed, 600)["kind"] == "test"


def test_identity_provider_cancellation_does_not_create_session(browser_login):
    fixture = browser_login
    _, query = begin(fixture)
    response = fixture.client.get(
        "/api/v1/auth/callback?" + urlencode({"state": query["state"][0], "error": "access_denied"})
    )
    assert response.status_code == 303
    assert response.headers["location"] == "https://app.example/"
    assert not fixture.captured and fixture.client.cookies.get(SESSION_COOKIE) is None
    assert fixture.client.cookies.get(LOGIN_COOKIE) is None


def test_machine_access_token_cannot_be_promoted_by_a_browser_callback(browser_login):
    fixture = browser_login
    fixture.token_changes["access_token"] = fixture.machine_token
    _, query = begin(fixture)
    response = callback(fixture, query["state"][0])
    assert response.status_code == 401
    assert fixture.client.cookies.get(SESSION_COOKIE) is None
