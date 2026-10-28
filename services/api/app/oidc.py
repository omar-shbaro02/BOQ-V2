"""Single-issuer access-token verification; membership and authority remain database-owned."""

import uuid
from functools import lru_cache
from urllib.parse import urlsplit

import jwt
from fastapi import HTTPException
from jwt import PyJWKClient

from app.config import Settings


def require_https(url: str) -> None:
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.fragment
            or parsed.query
        ):
            raise ValueError("Invalid adapter endpoint")
        _ = parsed.port
    except ValueError as exc:
        raise HTTPException(503, "Adapter endpoints must be configured with HTTPS") from exc


@lru_cache(maxsize=4)
def signing_keys(url: str, ttl: int, timeout: float) -> PyJWKClient:
    require_https(url)
    # Cache the set with a TTL, never individual keys indefinitely. Unknown kids have a cooldown.
    return PyJWKClient(url, lifespan=ttl, timeout=timeout, cache_keys=False, cooldown_duration=30)


def verified_claims(settings: Settings, authorization: str | None) -> dict:
    if not settings.oidc_issuer or not settings.oidc_audience or not settings.oidc_jwks_url:
        raise HTTPException(503, "OIDC identity adapter requires issuer, audience, and JWKS URL")
    require_https(settings.oidc_issuer)
    require_https(settings.oidc_jwks_url)
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            401, "Bearer access token required", headers={"WWW-Authenticate": "Bearer"}
        )
    token = authorization[7:]
    if not token or len(token) > 16384:
        raise HTTPException(401, "Invalid access token", headers={"WWW-Authenticate": "Bearer"})
    try:
        header = jwt.get_unverified_header(token)
        if (
            header.get("alg") != "RS256"
            or not isinstance(header.get("kid"), str)
            or not header["kid"]
        ):
            raise jwt.InvalidTokenError("Unsupported signing header")
        key = signing_keys(
            settings.oidc_jwks_url,
            settings.oidc_jwks_cache_seconds,
            settings.adapter_timeout_seconds,
        ).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],
            issuer=settings.oidc_issuer,
            audience=settings.oidc_audience,
            leeway=0,
            options={
                "require": ["exp", "iat", "iss", "aud", "sub", settings.oidc_organization_claim]
            },
        )
        subject = claims["sub"]
        if not isinstance(subject, str) or not subject.strip() or len(subject) > 200:
            raise ValueError("Invalid subject")
        uuid.UUID(claims[settings.oidc_organization_claim])
    except jwt.PyJWKClientConnectionError as exc:
        raise HTTPException(503, "Identity signing keys are unavailable") from exc
    except (jwt.PyJWTError, ValueError, TypeError, KeyError) as exc:
        raise HTTPException(
            401, "Invalid access token", headers={"WWW-Authenticate": "Bearer"}
        ) from exc
    return claims


def principal_type(settings: Settings, claims: dict) -> str:
    grant_type = claims.get("gty")
    if grant_type in ("client-credentials", "client_credentials"):
        return "SERVICE"
    if grant_type is not None and not isinstance(grant_type, str):
        return "UNKNOWN"
    value = claims.get(settings.oidc_principal_type_claim)
    return value if isinstance(value, str) and value in {"HUMAN", "SERVICE"} else "UNKNOWN"


def verify_identity(settings: Settings, authorization: str | None) -> tuple[str, uuid.UUID]:
    claims = verified_claims(settings, authorization)
    return claims["sub"], uuid.UUID(claims[settings.oidc_organization_claim])
