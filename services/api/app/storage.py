from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol

from fastapi import HTTPException

from app.config import get_settings


class EvidenceStore(Protocol):
    def put(self, key: str, content: bytes) -> None: ...

    def get(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...


class LocalEvidenceStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _resolve(self, key: str) -> Path:
        target = (self.root / key).resolve()
        if self.root not in target.parents:
            raise ValueError("Invalid evidence storage key")
        return target

    def put(self, key: str, content: bytes) -> None:
        target = self._resolve(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".partial")
        temporary.write_bytes(content)
        os.replace(temporary, target)

    def get(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    def delete(self, key: str) -> None:
        target = self._resolve(key)
        target.unlink(missing_ok=True)


def get_evidence_store() -> EvidenceStore:
    settings = get_settings()
    if settings.evidence_storage_backend != "local":
        raise HTTPException(status_code=503, detail="Configured evidence storage is unavailable")
    if settings.environment not in {"development", "test"}:
        raise HTTPException(status_code=503, detail="Production object storage adapter is required")
    return LocalEvidenceStore(settings.evidence_storage_path)
