import logging

from app.config import get_settings
from app.http_security import RedactAccessQuery, RequestSecurityMiddleware
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route


def bounded_app():
    async def echo(request):
        content = await request.body()
        return JSONResponse({"size": len(content)})

    return RequestSecurityMiddleware(
        Starlette(routes=[Route("/echo", echo, methods=["POST", "GET"])])
    )


def test_declared_and_actual_request_body_limits(monkeypatch):
    monkeypatch.setenv("VAI_MAX_REQUEST_BYTES", "1024")
    get_settings.cache_clear()
    with TestClient(bounded_app()) as client:
        assert client.post("/echo", content=b"small").json() == {"size": 5}
        assert client.post("/echo", content=b"x" * 1025).status_code == 413
        assert client.post("/echo", content=iter([b"x" * 600, b"y" * 600])).status_code == 413
        assert (
            client.post("/echo", content=b"x" * 1025, headers={"Content-Length": "1"}).status_code
            == 413
        )
        for value in ("invalid", "-1"):
            assert (
                client.post("/echo", content=b"", headers={"Content-Length": value}).status_code
                == 400
            )


def test_production_rate_limits_and_response_security_headers(monkeypatch):
    monkeypatch.setenv("VAI_ENVIRONMENT", "production")
    monkeypatch.setenv("VAI_RATE_LIMIT_PER_MINUTE", "2")
    get_settings.cache_clear()
    with TestClient(bounded_app()) as client:
        for expected in (200, 200, 429):
            response = client.get("/echo")
            assert response.status_code == expected
            assert response.headers["X-Content-Type-Options"] == "nosniff"
            assert response.headers["X-Frame-Options"] == "DENY"
            assert response.headers["Referrer-Policy"] == "no-referrer"
            assert response.headers["Cache-Control"] == "private, no-store"
            assert response.headers["Strict-Transport-Security"] == "max-age=31536000"
        assert response.headers["Retry-After"] == "60"


def test_rate_bucket_memory_and_window_are_bounded(monkeypatch):
    middleware = bounded_app()
    monkeypatch.setattr("app.http_security.time.monotonic", lambda: 100)
    for index in range(10000):
        assert middleware.allowed(str(index), 1)
    assert not middleware.allowed("new-address", 1)
    assert not middleware.allowed("0", 1)
    monkeypatch.setattr("app.http_security.time.monotonic", lambda: 200)
    assert middleware.allowed("new-address", 1)
    assert len(middleware.buckets) == 1


def test_auth_callback_query_is_redacted_from_access_logs():
    record = logging.LogRecord(
        "uvicorn.access",
        logging.INFO,
        "",
        0,
        '%s - "%s %s HTTP/%s" %d',
        ("client", "GET", "/api/v1/auth/callback?code=secret-code&state=secret-state", "1.1", 303),
        None,
    )
    assert RedactAccessQuery().filter(record)
    rendered = record.getMessage()
    assert "/api/v1/auth/callback" in rendered
    assert "secret-code" not in rendered and "secret-state" not in rendered
