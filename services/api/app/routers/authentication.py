import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Annotated
from urllib.parse import urlencode

import httpx
import jwt
from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Query, Response
from fastapi.responses import RedirectResponse
from starlette.concurrency import run_in_threadpool

from app.auth import ActorContext, get_actor
from app.config import get_settings
from app.oidc import principal_type, require_https, signing_keys, verified_claims
from app.web_sessions import (
    LOGIN_COOKIE,
    LOGIN_MAX_AGE,
    SESSION_COOKIE,
    public_origin,
    seal,
    session_cipher,
    unseal,
)

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


def browser_configuration():
    settings = get_settings()
    if settings.environment in {"development", "test"}:
        raise HTTPException(409, "OIDC browser sign-in is unavailable in the development profile")
    for value in (
        settings.oidc_authorization_url,
        settings.oidc_token_url,
        settings.oidc_issuer,
        settings.oidc_jwks_url,
    ):
        if not value:
            raise HTTPException(503, "OIDC browser sign-in is not configured")
        require_https(value)
    if not settings.oidc_client_id or not settings.oidc_client_secret or not settings.oidc_audience:
        raise HTTPException(503, "OIDC browser client configuration is required")
    session_cipher(settings)
    return settings, public_origin(settings)


@router.get("/session")
def session_status(
    authorization: Annotated[str | None, Header()] = None,
    session_cookie: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> dict:
    if get_settings().environment in {"development", "test"}:
        return {"mode": "DEVELOPMENT", "actor_id": None, "organization_id": None}
    actor = get_actor(None, None, None, authorization, session_cookie)
    return {
        "mode": "OIDC",
        "actor_id": actor.actor_id,
        "organization_id": str(actor.organization_id),
    }


@router.get("/login")
def begin_login() -> Response:
    settings, origin = browser_configuration()
    state, nonce, verifier = (
        secrets.token_urlsafe(32),
        secrets.token_urlsafe(32),
        secrets.token_urlsafe(48),
    )
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    transaction = seal(
        settings, {"kind": "login", "state": state, "nonce": nonce, "verifier": verifier}
    )
    query = urlencode(
        {
            "client_id": settings.oidc_client_id,
            "response_type": "code",
            "redirect_uri": origin + "/api/v1/auth/callback",
            "scope": "openid",
            "audience": settings.oidc_audience,
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    response = RedirectResponse(settings.oidc_authorization_url + "?" + query, status_code=303)
    response.set_cookie(
        LOGIN_COOKIE,
        transaction,
        max_age=LOGIN_MAX_AGE,
        secure=True,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


async def exchange_code(settings, code: str, verifier: str, origin: str) -> dict:
    try:
        async with (
            httpx.AsyncClient(
                timeout=settings.adapter_timeout_seconds, follow_redirects=False, trust_env=False
            ) as client,
            client.stream(
                "POST",
                settings.oidc_token_url,
                data={
                    "grant_type": "authorization_code",
                    "client_id": settings.oidc_client_id,
                    "client_secret": settings.oidc_client_secret.get_secret_value(),
                    "code": code,
                    "code_verifier": verifier,
                    "redirect_uri": origin + "/api/v1/auth/callback",
                },
            ) as response,
        ):
            if response.status_code != 200:
                raise ValueError("Identity exchange failed")
            data = bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                if len(data) > 65536:
                    raise ValueError("Oversized token response")
            result = json.loads(data)
            if not isinstance(result, dict):
                raise ValueError("Invalid token response")
            return result
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, "Identity token exchange is unavailable") from exc


@router.get("/callback")
async def finish_login(
    state: Annotated[str, Query(min_length=1, max_length=200)],
    code: Annotated[str | None, Query(min_length=1, max_length=2048)] = None,
    error: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    transaction_cookie: Annotated[str | None, Cookie(alias=LOGIN_COOKIE)] = None,
) -> Response:
    settings, origin = browser_configuration()
    if not transaction_cookie:
        raise HTTPException(401, "Browser login transaction is missing")
    transaction = unseal(settings, transaction_cookie, LOGIN_MAX_AGE)
    if (
        transaction.get("kind") != "login"
        or not all(
            isinstance(transaction.get(field), str) for field in ("state", "nonce", "verifier")
        )
        or not hmac.compare_digest(transaction["state"].encode(), state.encode())
    ):
        raise HTTPException(401, "Browser login state mismatch")
    if error is not None:
        response = RedirectResponse(origin + "/", status_code=303)
        response.delete_cookie(LOGIN_COOKIE, secure=True, httponly=True, samesite="lax", path="/")
        return response
    if code is None:
        raise HTTPException(401, "Browser authorization code is missing")
    tokens = await exchange_code(settings, code, transaction["verifier"], origin)
    try:
        access_token, id_token = tokens["access_token"], tokens["id_token"]
        if (
            not isinstance(tokens.get("token_type"), str)
            or tokens["token_type"].lower() != "bearer"
            or not isinstance(access_token, str)
            or not isinstance(id_token, str)
            or len(id_token) > 16384
        ):
            raise ValueError("Invalid token result")
        access_claims = await run_in_threadpool(verified_claims, settings, "Bearer " + access_token)
        if principal_type(settings, access_claims) == "SERVICE":
            raise ValueError("A machine access token cannot create a human browser session")
        actor_id = access_claims["sub"]
        # The ID token authenticates this browser client; only the access token authenticates APIs.
        if jwt.get_unverified_header(id_token).get("alg") != "RS256":
            raise ValueError("Invalid identity signing algorithm")
        keys = signing_keys(
            settings.oidc_jwks_url,
            settings.oidc_jwks_cache_seconds,
            settings.adapter_timeout_seconds,
        )
        key = await run_in_threadpool(keys.get_signing_key_from_jwt, id_token)
        identity = jwt.decode(
            id_token,
            key.key,
            algorithms=["RS256"],
            issuer=settings.oidc_issuer,
            audience=settings.oidc_client_id,
            options={"require": ["exp", "iat", "iss", "aud", "sub", "nonce"]},
        )
        if identity["sub"] != actor_id or not hmac.compare_digest(
            str(identity["nonce"]), transaction["nonce"]
        ):
            raise ValueError("Identity transaction mismatch")
        if (
            isinstance(identity.get("aud"), list)
            and len(identity["aud"]) > 1
            and identity.get("azp") != settings.oidc_client_id
        ):
            raise ValueError("Identity authorized party mismatch")
        if identity.get("azp", settings.oidc_client_id) != settings.oidc_client_id:
            raise ValueError("Identity authorized party mismatch")
        if "at_hash" in identity:
            expected_hash = (
                base64.urlsafe_b64encode(hashlib.sha256(access_token.encode()).digest()[:16])
                .rstrip(b"=")
                .decode()
            )
            if not isinstance(identity["at_hash"], str) or not hmac.compare_digest(
                identity["at_hash"], expected_hash
            ):
                raise ValueError("Identity access-token binding mismatch")
        lifetime = tokens["expires_in"]
        if not isinstance(lifetime, int) or isinstance(lifetime, bool) or lifetime <= 0:
            raise ValueError("Invalid access-token lifetime")
        expires = min(
            int(access_claims["exp"]),
            int(identity["exp"]),
            int(time.time()) + lifetime,
            int(time.time()) + settings.session_max_age_seconds,
        )
        value = seal(
            settings, {"kind": "session", "access_token": access_token, "expires": expires}
        )
    except jwt.PyJWKClientConnectionError as exc:
        raise HTTPException(503, "Identity signing keys are unavailable") from exc
    except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise HTTPException(401, "Identity login response failed verification") from exc
    response = RedirectResponse(origin + "/", status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        value,
        max_age=max(1, expires - int(time.time())),
        secure=True,
        httponly=True,
        samesite="lax",
        path="/",
    )
    response.delete_cookie(LOGIN_COOKIE, secure=True, httponly=True, samesite="lax", path="/")
    return response


@router.post("/logout", status_code=204)
def end_session(actor: Annotated[ActorContext, Depends(get_actor)]) -> Response:
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, secure=True, httponly=True, samesite="lax", path="/")
    response.delete_cookie(LOGIN_COOKIE, secure=True, httponly=True, samesite="lax", path="/")
    return response
