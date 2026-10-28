"""Short-lived encrypted browser sessions; tokens never enter browser JavaScript storage."""

import json
import time
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from fastapi import HTTPException

from app.config import Settings
from app.oidc import require_https

SESSION_COOKIE = "__Host-vai-session"
LOGIN_COOKIE = "__Host-vai-login"
LOGIN_MAX_AGE = 600


def session_cipher(settings: Settings) -> MultiFernet:
    if not settings.session_encryption_keys:
        raise HTTPException(503, "Browser session encryption is not configured")
    try:
        return MultiFernet(
            [Fernet(key.get_secret_value().encode()) for key in settings.session_encryption_keys]
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(503, "Browser session encryption configuration is invalid") from exc


def public_origin(settings: Settings) -> str:
    origin = settings.session_public_origin
    if not origin:
        raise HTTPException(503, "Browser session public HTTPS origin is required")
    require_https(origin)
    if urlsplit(origin).path not in {"", "/"}:
        raise HTTPException(503, "Browser session origin must not include a path")
    return origin.rstrip("/")


def seal(settings: Settings, payload: dict) -> str:
    value = (
        session_cipher(settings)
        .encrypt(json.dumps(payload, separators=(",", ":")).encode())
        .decode()
    )
    if len(value) > 3800:
        raise HTTPException(503, "Identity claims exceed the browser session resource limit")
    return value


def unseal(settings: Settings, value: str, ttl: int) -> dict:
    if len(value) > 3800:
        raise HTTPException(401, "Browser session is invalid or expired")
    try:
        data = json.loads(session_cipher(settings).decrypt(value.encode(), ttl=ttl))
        if not isinstance(data, dict):
            raise ValueError("Invalid session shape")
        return data
    except (InvalidToken, ValueError, TypeError, UnicodeError) as exc:
        raise HTTPException(401, "Browser session is invalid or expired") from exc


def session_access_token(settings: Settings, cookie: str) -> str:
    data = unseal(settings, cookie, settings.session_max_age_seconds)
    if (
        data.get("kind") != "session"
        or not isinstance(data.get("expires"), int)
        or data["expires"] <= time.time()
        or not isinstance(data.get("access_token"), str)
    ):
        raise HTTPException(401, "Browser session is invalid or expired")
    return data["access_token"]
