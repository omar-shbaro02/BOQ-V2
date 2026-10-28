"""Isolated HTTPS OIDC issuer + production-profile API for browser verification only."""

import base64
import hashlib
import hmac
import json
import os
import secrets
import ssl
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlencode

import httpx
import jwt
import uvicorn
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api"))


def main():
    if os.environ.get("VAI_SYNTHETIC_OIDC_REHEARSAL") != "isolated-loopback-only":
        raise RuntimeError("This synthetic identity provider is not an application adapter")
    from sqlalchemy.engine import make_url

    database = make_url(os.environ["VAI_DATABASE_URL"])
    if (
        database.drivername != "sqlite+pysqlite"
        or (ROOT / ".test-tmp").resolve() not in Path(database.database).resolve().parents
    ):
        raise RuntimeError("Synthetic identity tests require disposable workspace SQLite storage")
    from app.database import Base, engine
    from app.main import app
    from app.models import DecisionCaseShell, Membership, Organization, Project
    from fastapi import HTTPException, Request
    from fastapi.responses import RedirectResponse
    from sqlalchemy.orm import Session

    Base.metadata.create_all(engine)
    organization, project = uuid.UUID(int=201), uuid.UUID(int=202)
    subject = "auth0|browser-operator"
    with Session(engine) as session:
        session.add(
            Organization(id=organization, name="Synthetic identity fixture", slug="oidc-browser")
        )
        session.flush()
        session.add(
            Project(
                id=project,
                organization_id=organization,
                code="OIDC",
                name="Signed-in project",
                timezone="Asia/Beirut",
                currency="USD",
                delivery_model="DESIGN_BID_BUILD",
                reporting_cadence="WEEKLY",
            )
        )
        session.flush()
        session.add(
            Membership(
                organization_id=organization,
                project_id=project,
                actor_id=subject,
                role="PROJECT_ADMIN",
            )
        )
        session.add(
            DecisionCaseShell(
                organization_id=organization,
                project_id=project,
                case_number="DC-OIDC-001",
                title="Identity fixture case",
                case_type="PROGRESS",
                lifecycle="OPEN",
                owner_actor_id=subject,
                created_by=subject,
                governance_state="HUMAN_REVIEW_REQUIRED",
            )
        )
        session.commit()
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    public_key.update(kid="synthetic-key", alg="RS256", use="sig")
    codes = {}

    @app.get("/fixture/keys")
    def keys():
        return {"keys": [public_key]}

    @app.post("/api/v1/fixture/body-size")
    async def body_size(request: Request):
        return {"size": len(await request.body())}

    @app.get("/fixture/authorize")
    def authorize(request: Request):
        query = request.query_params
        if (
            query.get("client_id") != "synthetic-browser"
            or query.get("redirect_uri") != "https://127.0.0.1:3012/api/v1/auth/callback"
            or query.get("code_challenge_method") != "S256"
            or query.get("response_type") != "code"
            or query.get("audience") != "synthetic-vai-api"
        ):
            raise HTTPException(400, "Invalid synthetic client request")
        code = secrets.token_urlsafe(32)
        codes[code] = {**dict(query), "created": time.time()}
        return RedirectResponse(
            query["redirect_uri"] + "?" + urlencode({"code": code, "state": query["state"]}),
            status_code=303,
        )

    @app.post("/fixture/token")
    async def token(request: Request):
        form = await request.form()
        transaction = codes.pop(str(form.get("code")), None)
        challenge = (
            base64.urlsafe_b64encode(
                hashlib.sha256(str(form.get("code_verifier")).encode()).digest()
            )
            .rstrip(b"=")
            .decode()
        )
        if (
            not transaction
            or time.time() - transaction["created"] > 60
            or not hmac.compare_digest(
                str(form.get("client_secret")), os.environ["VAI_OIDC_CLIENT_SECRET"]
            )
            or form.get("grant_type") != "authorization_code"
            or form.get("client_id") != "synthetic-browser"
            or form.get("redirect_uri") != transaction["redirect_uri"]
            or challenge != transaction["code_challenge"]
        ):
            raise HTTPException(400, "Invalid synthetic code exchange")
        now = int(time.time())
        common = {
            "iss": os.environ["VAI_OIDC_ISSUER"],
            "sub": subject,
            "iat": now,
            "exp": now + 600,
        }
        access = jwt.encode(
            {
                **common,
                "aud": "synthetic-vai-api",
                "https://vai.example/organization_id": str(organization),
            },
            private,
            algorithm="RS256",
            headers={"kid": "synthetic-key"},
        )
        binding = (
            base64.urlsafe_b64encode(hashlib.sha256(access.encode()).digest()[:16])
            .rstrip(b"=")
            .decode()
        )
        identity = jwt.encode(
            {
                **common,
                "aud": "synthetic-browser",
                "nonce": transaction["nonce"],
                "at_hash": binding,
            },
            private,
            algorithm="RS256",
            headers={"kid": "synthetic-key"},
        )
        return {
            "access_token": access,
            "id_token": identity,
            "token_type": "Bearer",
            "expires_in": 600,
        }

    # Only this disposable fixture trusts the generated test CA. Production defaults are unchanged.
    original_client = httpx.AsyncClient
    context = ssl.create_default_context(cafile=os.environ["SSL_CERT_FILE"])
    httpx.AsyncClient = lambda **kwargs: original_client(**kwargs, verify=context)
    try:
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8012,
            ssl_keyfile=os.environ["VAI_TEST_TLS_KEY"],
            ssl_certfile=os.environ["SSL_CERT_FILE"],
        )
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
