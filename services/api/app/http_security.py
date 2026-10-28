"""Bound request resources and protect cookie-authenticated commands before domain handlers."""

import logging
import threading
import time

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse

from app.config import get_settings
from app.web_sessions import SESSION_COOKIE


class BodyLimitExceeded(Exception):
    pass


class RequestSecurityMiddleware:
    def __init__(self, app):
        self.app = app
        self.buckets = {}
        self.lock = threading.Lock()
        self.last_window = None

    def allowed(self, client: str, limit: int) -> bool:
        window = (int(time.monotonic() // 60), limit)
        with self.lock:
            if self.last_window != window:
                self.buckets.clear()
                self.last_window = window
            if client not in self.buckets and len(self.buckets) >= 10000:
                return False
            count = self.buckets.get(client, 0) + 1
            self.buckets[client] = count
            return count <= limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        settings = get_settings()
        production = settings.environment not in {"development", "test"}
        headers = Headers(scope=scope)
        oversized = False
        sent_limit = False
        started = False

        async def secure_send(message):
            nonlocal sent_limit, started
            if oversized:
                if not sent_limit:
                    sent_limit = True
                    await JSONResponse({"detail": "Request exceeds body resource limit"}, 413)(
                        scope, receive, protected_send
                    )
                return
            await protected_send(message)

        async def protected_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                output = MutableHeaders(scope=message)
                output["X-Content-Type-Options"] = "nosniff"
                output["X-Frame-Options"] = "DENY"
                output["Referrer-Policy"] = "no-referrer"
                output["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                output["Cache-Control"] = "private, no-store"
                if scope["path"].startswith("/api/") or scope["path"] == "/health":
                    output["Content-Security-Policy"] = (
                        "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
                    )
                if production:
                    output["Strict-Transport-Security"] = "max-age=31536000"
            await send(message)

        async def reject(code, detail, extra=None):
            await JSONResponse({"detail": detail}, code, headers=extra)(scope, receive, secure_send)

        if production and not self.allowed(
            (scope.get("client") or ("unknown",))[0], settings.rate_limit_per_minute
        ):
            return await reject(429, "Request rate limit exceeded", {"Retry-After": "60"})
        if (
            production
            and scope["method"] not in {"GET", "HEAD", "OPTIONS"}
            and SESSION_COOKIE + "=" in headers.get("cookie", "")
            and not headers.get("authorization")
        ):
            expected = (settings.session_public_origin or "").rstrip("/")
            if not expected or headers.get("origin") != expected:
                return await reject(
                    403, "Same-origin request required for browser session commands"
                )
        length = headers.get("content-length")
        if length is not None:
            try:
                size = int(length)
                if size < 0:
                    raise ValueError("Invalid length")
            except ValueError:
                return await reject(400, "Invalid Content-Length")
            if size > settings.max_request_bytes:
                return await reject(413, "Request exceeds body resource limit")
        received = 0

        async def bounded_receive():
            nonlocal received, oversized
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > settings.max_request_bytes:
                    oversized = True
                    raise BodyLimitExceeded()
            return message

        try:
            await self.app(scope, bounded_receive, secure_send)
        except BodyLimitExceeded:
            if not started:
                await reject(413, "Request exceeds body resource limit")


class RedactAccessQuery(logging.Filter):
    def filter(self, record):
        if isinstance(record.args, tuple) and len(record.args) == 5:
            client, method, target, version, status = record.args
            record.args = (client, method, str(target).split("?", 1)[0], version, status)
        return True
