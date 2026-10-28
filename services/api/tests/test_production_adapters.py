import hashlib
import io
import json
import socket
import struct
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import jwt
import pytest
from app.auth import get_actor
from app.config import Settings, get_settings
from app.oidc import signing_keys, verify_identity
from app.security_scan import ClamdEvidenceScanner, get_evidence_scanner
from app.storage import S3EvidenceStore, get_evidence_store
from botocore.exceptions import ClientError
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException


@pytest.fixture
def identity(monkeypatch):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    org = uuid.uuid4()
    settings = Settings(
        _env_file=None,
        oidc_issuer="https://login.example/",
        oidc_audience="vai-api",
        oidc_jwks_url="https://login.example/keys",
    )
    now = int(time.time())
    claims = {
        "iss": settings.oidc_issuer,
        "aud": settings.oidc_audience,
        "sub": "auth0|stable-subject",
        "exp": now + 300,
        "iat": now - 1,
        settings.oidc_organization_claim: str(org),
    }
    client = Mock()
    client.get_signing_key_from_jwt.return_value = SimpleNamespace(key=private.public_key())
    monkeypatch.setattr("app.oidc.signing_keys", lambda *args: client)

    def token(changes=None, key=None, drop=(), **kwargs):
        payload = {**claims, **(changes or {})}
        for field in drop:
            payload.pop(field, None)
        return jwt.encode(
            payload,
            key or private,
            algorithm="RS256",
            headers={"kid": "active-key"},
            **kwargs,
        )

    return settings, org, token, client


def test_oidc_valid_identity_ignores_header_impersonation_and_roles(identity, monkeypatch):
    settings, org, token, _ = identity
    monkeypatch.setenv("VAI_ENVIRONMENT", "production")
    monkeypatch.setenv("VAI_OIDC_ISSUER", settings.oidc_issuer)
    monkeypatch.setenv("VAI_OIDC_AUDIENCE", settings.oidc_audience)
    monkeypatch.setenv("VAI_OIDC_JWKS_URL", settings.oidc_jwks_url)
    get_settings.cache_clear()
    actor = get_actor("forged-admin", org, "ORGANIZATION_ADMIN", f"Bearer {token()}")
    assert actor.actor_id == "auth0|stable-subject"
    assert actor.organization_id == org
    assert not actor.asserted_roles
    with pytest.raises(HTTPException) as denied:
        get_actor("forged-admin", uuid.uuid4(), "ORGANIZATION_ADMIN", f"Bearer {token()}")
    assert denied.value.status_code == 403


@pytest.mark.parametrize(
    "changes",
    [
        {"iss": "https://evil.example/"},
        {"aud": "other-api"},
        {"exp": 1},
        {"iat": 9999999999},
        {"nbf": 9999999999},
        {"sub": ""},
        {"https://vai.example/organization_id": "other-tenant"},
    ],
)
def test_oidc_invalid_claims_fail_closed(identity, changes):
    settings, _, token, _ = identity
    with pytest.raises(HTTPException) as denied:
        verify_identity(settings, f"Bearer {token(changes)}")
    assert denied.value.status_code == 401


def test_oidc_signature_algorithm_missing_claim_and_outage(identity):
    settings, _, token, client = identity
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    for bad in (
        token(key=other),
        token(drop=("exp",)),
        token(drop=("iat",)),
        token(drop=(settings.oidc_organization_claim,)),
        jwt.encode({"sub": "forged"}, "test" * 16, algorithm="HS256", headers={"kid": "x"}),
        "",
        "broken",
    ):
        with pytest.raises(HTTPException) as denied:
            verify_identity(settings, f"Bearer {bad}")
        assert denied.value.status_code == 401
    client.get_signing_key_from_jwt.side_effect = jwt.PyJWKClientConnectionError(
        "unavailable secret URL"
    )
    with pytest.raises(HTTPException) as outage:
        verify_identity(settings, f"Bearer {token()}")
    assert outage.value.status_code == 503
    assert "secret" not in outage.value.detail


def test_jwks_cache_is_finite_and_unknown_key_refresh_is_bounded(monkeypatch):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    jwk.update(kid="known", alg="RS256", use="sig")
    calls = []

    def open_keys(*args, **kwargs):
        calls.append(1)
        return io.BytesIO(json.dumps({"keys": [jwk]}).encode())

    monkeypatch.setattr("urllib.request.OpenerDirector.open", open_keys)
    signing_keys.cache_clear()
    client = signing_keys("https://login.example/keys", 300, 2)
    assert client.get_signing_key("known").key_id == "known"
    assert client.get_signing_key("known").key_id == "known"
    for _ in range(3):
        with pytest.raises(jwt.PyJWKClientError):
            client.get_signing_key("unknown")
    assert len(calls) == 1
    assert client.jwk_set_cache.lifespan == 300
    signing_keys.cache_clear()


def object_response(content, metadata=None, length=None):
    return {
        "Body": io.BytesIO(content),
        "ContentLength": len(content) if length is None else length,
        "Metadata": metadata
        if metadata is not None
        else {"sha256": hashlib.sha256(content).hexdigest()},
    }


def test_s3_encrypted_conditional_write_replay_and_integrity():
    client = Mock()
    store = S3EvidenceStore(client, "private-bucket", "vai/", 1000, "kms-key")
    store.put("org/project/artifact/file", b"evidence")
    args = client.put_object.call_args.kwargs
    assert args["IfNoneMatch"] == "*"
    assert args["ServerSideEncryption"] == "aws:kms"
    assert args["SSEKMSKeyId"] == "kms-key"
    assert args["Key"] == "vai/org/project/artifact/file"
    client.put_object.side_effect = ClientError(
        {"ResponseMetadata": {"HTTPStatusCode": 412}}, "PutObject"
    )
    client.get_object.return_value = object_response(b"evidence")
    store.put("org/project/artifact/file", b"evidence")
    client.get_object.return_value = object_response(b"other")
    with pytest.raises(HTTPException) as mismatch:
        store.put("org/project/artifact/file", b"evidence")
    assert mismatch.value.status_code == 409
    for response in (
        object_response(b"tampered", {"sha256": "bad"}),
        object_response(b"x", {}),
        object_response(b"x", length=2),
    ):
        client.get_object.return_value = response
        with pytest.raises(HTTPException) as corrupt:
            store.get("org/project/artifact/file")
        assert corrupt.value.status_code == 409
        assert response["Body"].closed


def test_s3_bounds_keys_outage_and_missing_objects():
    client = Mock()
    store = S3EvidenceStore(client, "private-bucket", "vai/", 3)
    for bad in ("../outside", "/absolute", "org//key", "org\\key"):
        with pytest.raises(ValueError):
            store.get(bad)
    with pytest.raises(HTTPException) as oversized:
        store.put("org/file", b"large")
    assert oversized.value.status_code == 413
    client.get_object.return_value = object_response(b"1234")
    with pytest.raises(HTTPException) as oversized:
        store.get("org/file")
    assert oversized.value.status_code == 413
    client.get_object.side_effect = ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
    with pytest.raises(FileNotFoundError):
        store.get("org/file")
    client.get_object.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "secret"}}, "GetObject"
    )
    with pytest.raises(HTTPException) as unavailable:
        store.get("org/file")
    assert unavailable.value.status_code == 503
    assert "secret" not in unavailable.value.detail


def clamd_server(reply=b"stream: OK\0", old=False):
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(2)
    listener.settimeout(2)
    received = bytearray()

    def exact(connection, size):
        result = bytearray()
        while len(result) < size:
            chunk = connection.recv(size - len(result))
            if not chunk:
                raise ValueError("Unexpected EOF")
            result.extend(chunk)
        return bytes(result)

    def serve():
        try:
            for _ in range(1 if old else 2):
                with listener.accept()[0] as connection:
                    connection.settimeout(2)
                    command = bytearray()
                    while not command.endswith(b"\0"):
                        command.extend(exact(connection, 1))
                    if command == b"zVERSION\0":
                        built = datetime.now(UTC) - timedelta(days=7 if old else 0)
                        stamp = built.strftime("%a %b %d %H:%M:%S %Y")
                        connection.sendall(f"ClamAV 1.4.3/28000/{stamp}\0".encode())
                    else:
                        assert command == b"zINSTREAM\0"
                        while length := struct.unpack("!I", exact(connection, 4))[0]:
                            received.extend(exact(connection, length))
                        connection.sendall(reply)
        finally:
            listener.close()

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    return listener.getsockname()[1], received, thread


@pytest.mark.parametrize(
    "reply,status",
    [
        (b"stream: OK\0", None),
        (b"stream: Eicar FOUND\0", 422),
        (b"INSTREAM size limit exceeded. ERROR\0", 503),
        (b"stream: OK", 503),
    ],
)
def test_clamd_stream_protocol_clean_infected_and_incomplete(reply, status):
    port, received, thread = clamd_server(reply)
    scanner = ClamdEvidenceScanner("127.0.0.1", port, 2, 48)
    content = b"evidence" * 10000
    if status:
        with pytest.raises(HTTPException) as denied:
            scanner.scan("untrusted-name", content)
        assert denied.value.status_code == status
    else:
        result = scanner.scan("untrusted-name", content)
        assert result.result == "CLEAN" and result.signature_version.startswith("28000/")
    thread.join(3)
    assert not thread.is_alive()
    assert received == content


def test_clamd_stale_signatures_and_unconfigured_production_fail_closed(monkeypatch):
    port, received, thread = clamd_server(old=True)
    with pytest.raises(HTTPException) as stale:
        ClamdEvidenceScanner("127.0.0.1", port, 2, 48).scan("file", b"content")
    assert stale.value.status_code == 503
    thread.join(3)
    assert not received
    monkeypatch.setenv("VAI_ENVIRONMENT", "production")
    get_settings.cache_clear()
    for factory in (get_evidence_store, get_evidence_scanner):
        with pytest.raises(HTTPException) as denied:
            factory()
        assert denied.value.status_code == 503
    with pytest.raises(HTTPException) as denied:
        verify_identity(Settings(_env_file=None), None)
    assert denied.value.status_code == 503
