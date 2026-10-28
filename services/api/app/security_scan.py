from __future__ import annotations

import socket
import struct
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from fastapi import HTTPException

from app.config import get_settings

ALLOWED_EVIDENCE_EXTENSIONS = {
    ".csv",
    ".json",
    ".jpeg",
    ".jpg",
    ".pdf",
    ".png",
    ".txt",
    ".webp",
    ".xlsm",
    ".xlsx",
}
EICAR_MARKER = b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE"


@dataclass(frozen=True, slots=True)
class ScanResult:
    result: str
    engine: str
    signature_version: str
    scanned_at: datetime


class EvidenceScanner(Protocol):
    def scan(self, filename: str, content: bytes) -> ScanResult: ...


def validate_evidence_type(filename: str, content: bytes) -> None:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EVIDENCE_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Evidence file type is not allowed")
    signatures = {
        ".pdf": content.startswith(b"%PDF"),
        ".png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        ".jpg": content.startswith(b"\xff\xd8\xff"),
        ".jpeg": content.startswith(b"\xff\xd8\xff"),
        ".webp": content.startswith(b"RIFF") and content[8:12] == b"WEBP",
        ".xlsx": content.startswith(b"PK"),
        ".xlsm": content.startswith(b"PK"),
    }
    if suffix in signatures and not signatures[suffix]:
        raise HTTPException(status_code=415, detail="File content does not match its extension")
    if suffix in {".xlsx", ".xlsm"}:
        from app.archive_limits import validate_workbook_archive

        try:
            validate_workbook_archive(content)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
    if suffix in {".csv", ".json", ".txt"}:
        try:
            content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=415, detail="Text evidence must be UTF-8") from exc


class DevelopmentEvidenceScanner:
    """Safe development gate; production requires a maintained malware engine adapter."""

    def scan(self, filename: str, content: bytes) -> ScanResult:
        del filename
        if EICAR_MARKER in content:
            raise HTTPException(status_code=422, detail="Evidence artifact failed malware scan")
        return ScanResult(
            result="CLEAN",
            engine="DEVELOPMENT_EICAR_GATE",
            signature_version="EICAR-1",
            scanned_at=datetime.now(UTC),
        )


class ClamdEvidenceScanner:
    def __init__(self, host: str, port: int, timeout: float, max_age_hours: int):
        self.host, self.port, self.timeout, self.max_age_hours = host, port, timeout, max_age_hours

    def _command(self, command: bytes, deadline: float, content: bytes | None = None) -> str:
        def remaining():
            value = deadline - time.monotonic()
            if value <= 0:
                raise TimeoutError("Scanner deadline exceeded")
            return value

        with socket.create_connection((self.host, self.port), timeout=remaining()) as connection:
            connection.settimeout(remaining())
            connection.sendall(command)
            if content is not None:
                for offset in range(0, len(content), 65536):
                    connection.settimeout(remaining())
                    chunk = content[offset : offset + 65536]
                    connection.sendall(struct.pack("!I", len(chunk)) + chunk)
                connection.settimeout(remaining())
                connection.sendall(b"\x00\x00\x00\x00")
            response = bytearray()
            while len(response) <= 4096:
                connection.settimeout(remaining())
                chunk = connection.recv(4097 - len(response))
                if not chunk:
                    break
                response.extend(chunk)
                if b"\x00" in response:
                    return response.split(b"\x00", 1)[0].decode("ascii")
            raise ValueError("Malformed scanner response")

    def scan(self, filename: str, content: bytes) -> ScanResult:
        del filename
        deadline = time.monotonic() + self.timeout
        try:
            version = self._command(b"zVERSION\x00", deadline)
            engine, signatures, built = version.split("/", 2)
            if not engine.startswith("ClamAV ") or not signatures.isdigit():
                raise ValueError("Invalid scanner version")
            # Deploy clamd with TZ=UTC; VERSION database timestamps have no timezone marker.
            signature_date = datetime.strptime(built.strip(), "%a %b %d %H:%M:%S %Y").replace(
                tzinfo=UTC
            )
            age = (datetime.now(UTC) - signature_date).total_seconds()
            if age < -300 or age > self.max_age_hours * 3600:
                raise ValueError("Scanner signatures are stale or future-dated")
            outcome = self._command(b"zINSTREAM\x00", deadline, content)
            if outcome.endswith(" FOUND"):
                raise HTTPException(422, "Evidence artifact failed malware scan")
            if outcome != "stream: OK":
                raise ValueError("Scanner did not confirm a complete clean scan")
            signature_version = f"{signatures}/{built}"
            if len(engine) > 80 or len(signature_version) > 80:
                raise ValueError("Scanner version cannot be stored without losing provenance")
            return ScanResult("CLEAN", engine, signature_version, datetime.now(UTC))
        except (OSError, ValueError, UnicodeError) as exc:
            raise HTTPException(
                503, "Malware scanner is unavailable or cannot verify a complete scan"
            ) from exc


def get_evidence_scanner() -> EvidenceScanner:
    settings = get_settings()
    if settings.malware_scanner_backend == "clamd":
        if not settings.clamd_host:
            raise HTTPException(503, "ClamAV daemon host is required")
        return ClamdEvidenceScanner(
            settings.clamd_host,
            settings.clamd_port,
            settings.adapter_timeout_seconds,
            settings.clamd_max_signature_age_hours,
        )
    if (
        settings.environment not in {"development", "test"}
        or settings.malware_scanner_backend != "development"
    ):
        raise HTTPException(
            status_code=503, detail="Production malware scanner adapter is required"
        )
    return DevelopmentEvidenceScanner()
