from __future__ import annotations

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


def get_evidence_scanner() -> EvidenceScanner:
    if get_settings().environment not in {"development", "test"}:
        raise HTTPException(
            status_code=503, detail="Production malware scanner adapter is required"
        )
    return DevelopmentEvidenceScanner()
