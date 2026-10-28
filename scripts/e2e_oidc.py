"""Run a disposable production web/API + synthetic OIDC issuer with real loopback TLS."""

import ipaddress
import json
import os
import secrets
import subprocess
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

ROOT = Path(__file__).resolve().parents[1]


def main():
    scratch = ROOT / ".test-tmp"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="oidc-browser-", dir=scratch) as directory:
        folder = Path(directory)
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        name = x509.Name(
            [x509.NameAttribute(NameOID.COMMON_NAME, "Disposable VAI loopback test CA")]
        )
        now = datetime.now(UTC)
        certificate = (
            x509.CertificateBuilder()
            .subject_name(name)
            .issuer_name(name)
            .public_key(private.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=1))
            .not_valid_after(now + timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(
                x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]),
                critical=False,
            )
            .sign(private, hashes.SHA256())
        )
        key, cert = folder / "tls-key.pem", folder / "tls-ca.pem"
        key.write_bytes(
            private.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            )
        )
        cert.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
        environment = {
            **os.environ,
            "VAI_ENVIRONMENT": "production",
            "VAI_SYNTHETIC_OIDC_REHEARSAL": "isolated-loopback-only",
            "VAI_DATABASE_URL": f"sqlite+pysqlite:///{folder / 'database.db'}",
            "VAI_EVIDENCE_STORAGE_PATH": str(folder / "evidence"),
            "VAI_OPENAI_API_KEY": "",
            "VAI_OPENAI_AGENTS_ENABLED": "false",
            "VAI_OIDC_ISSUER": "https://127.0.0.1:8012/fixture",
            "VAI_OIDC_AUDIENCE": "synthetic-vai-api",
            "VAI_OIDC_JWKS_URL": "https://127.0.0.1:8012/fixture/keys",
            "VAI_OIDC_CLIENT_ID": "synthetic-browser",
            "VAI_OIDC_CLIENT_SECRET": secrets.token_urlsafe(32),
            "VAI_OIDC_AUTHORIZATION_URL": "https://127.0.0.1:8012/fixture/authorize",
            "VAI_OIDC_TOKEN_URL": "https://127.0.0.1:8012/fixture/token",
            "VAI_SESSION_PUBLIC_ORIGIN": "https://127.0.0.1:3012",
            "VAI_SESSION_ENCRYPTION_KEYS": json.dumps([Fernet.generate_key().decode()]),
            "VAI_RATE_LIMIT_PER_MINUTE": "1000",
            "NEXT_PUBLIC_VAI_API_URL": "",
            "VAI_API_INTERNAL_URL": "https://127.0.0.1:8012",
            "VAI_TEST_TLS_KEY": str(key),
            "SSL_CERT_FILE": str(cert),
            "NODE_EXTRA_CA_CERTS": str(cert),
        }
        options = {"cwd": str(ROOT), "env": environment}
        if os.name == "nt":
            options["creationflags"] = subprocess.CREATE_NO_WINDOW
        children = []
        try:
            children.append(
                subprocess.Popen([sys.executable, "scripts/e2e_oidc_api.py"], **options)
            )
            subprocess.run(
                ["node", "apps/web/node_modules/next/dist/bin/next", "build", "apps/web"],
                check=True,
                **options,
            )
            children.append(
                subprocess.Popen(
                    [
                        "node",
                        "apps/web/node_modules/next/dist/bin/next",
                        "start",
                        "apps/web",
                        "--hostname",
                        "127.0.0.1",
                        "--port",
                        "3013",
                    ],
                    **options,
                )
            )
            children.append(subprocess.Popen(["node", "scripts/e2e_https_proxy.cjs"], **options))
            children[-1].wait()
        finally:
            for child in reversed(children):
                if child.poll() is None:
                    child.terminate()
            for child in children:
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()


if __name__ == "__main__":
    main()
