from __future__ import annotations

import hashlib
import os
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from fastapi import HTTPException

from app.config import get_settings


class EvidenceStore(Protocol):
    def put(self, key: str, content: bytes) -> None: ...

    def get(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None: ...


def validate_key(key: str) -> str:
    if not key or "\\" in key or any(part in {"", ".", ".."} for part in key.split("/")):
        raise ValueError("Invalid evidence storage key")
    return key


class LocalEvidenceStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _resolve(self, key: str) -> Path:
        validate_key(key)
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


class S3EvidenceStore:
    def __init__(
        self, client, bucket: str, prefix: str, max_bytes: int, kms_key: str | None = None
    ):
        self.client, self.bucket = client, bucket
        self.prefix = prefix.rstrip("/") + "/" if prefix else ""
        if self.prefix:
            validate_key(self.prefix[:-1])
        self.max_bytes, self.kms_key = max_bytes, kms_key

    def _key(self, key: str) -> str:
        return self.prefix + validate_key(key)

    def put(self, key: str, content: bytes) -> None:
        from botocore.exceptions import BotoCoreError, ClientError

        object_key = self._key(key)
        if len(content) > self.max_bytes:
            raise HTTPException(413, "Artifact exceeds storage resource limit")
        digest = hashlib.sha256(content).hexdigest()
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=object_key,
                Body=content,
                IfNoneMatch="*",
                Metadata={"sha256": digest},
                ServerSideEncryption="aws:kms" if self.kms_key else "AES256",
                **({"SSEKMSKeyId": self.kms_key} if self.kms_key else {}),
            )
        except ClientError as exc:
            if exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 412:
                if self.get(key) == content:
                    return
                raise HTTPException(
                    409, "Immutable object key already exists with different content"
                ) from exc
            raise HTTPException(503, "Object storage write unavailable") from exc
        except BotoCoreError as exc:
            raise HTTPException(503, "Object storage write unavailable") from exc

    def get(self, key: str) -> bytes:
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            response = self.client.get_object(Bucket=self.bucket, Key=self._key(key))
            stream = response["Body"]
            try:
                if response["ContentLength"] > self.max_bytes:
                    raise HTTPException(413, "Stored artifact exceeds resource limit")
                content = stream.read(self.max_bytes + 1)
            finally:
                stream.close()
            if len(content) > self.max_bytes:
                raise HTTPException(413, "Stored artifact exceeds resource limit")
            if len(content) != response["ContentLength"]:
                raise HTTPException(409, "Stored object length mismatch")
            expected = response.get("Metadata", {}).get("sha256")
            if not expected or hashlib.sha256(content).hexdigest() != expected:
                raise HTTPException(409, "Stored object integrity mismatch")
            return content
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "404"}:
                raise FileNotFoundError(key) from exc
            raise HTTPException(503, "Object storage read unavailable") from exc
        except (BotoCoreError, OSError) as exc:
            raise HTTPException(503, "Object storage read unavailable") from exc

    def delete(self, key: str) -> None:
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            # Transaction-failure cleanup only. Versioned buckets retain prior object versions.
            self.client.delete_object(Bucket=self.bucket, Key=self._key(key))
        except (BotoCoreError, ClientError) as exc:
            raise HTTPException(503, "Object storage cleanup unavailable") from exc


@lru_cache(maxsize=4)
def s3_client(region: str, endpoint: str | None, timeout: float):
    import boto3
    from botocore.config import Config

    return boto3.client(
        "s3",
        region_name=region,
        endpoint_url=endpoint,
        config=Config(
            connect_timeout=timeout,
            read_timeout=timeout,
            retries={"total_max_attempts": 2, "mode": "standard"},
        ),
    )


def get_evidence_store() -> EvidenceStore:
    settings = get_settings()
    if settings.evidence_storage_backend == "s3":
        if not settings.s3_bucket or not settings.s3_region:
            raise HTTPException(503, "S3 storage requires bucket and region")
        if settings.s3_endpoint_url:
            from app.oidc import require_https

            require_https(settings.s3_endpoint_url)
        return S3EvidenceStore(
            s3_client(
                settings.s3_region, settings.s3_endpoint_url, settings.adapter_timeout_seconds
            ),
            settings.s3_bucket,
            settings.s3_prefix,
            settings.max_artifact_bytes,
            settings.s3_kms_key_id,
        )
    if settings.evidence_storage_backend != "local":
        raise HTTPException(status_code=503, detail="Configured evidence storage is unavailable")
    if settings.environment not in {"development", "test"}:
        raise HTTPException(status_code=503, detail="Production object storage adapter is required")
    return LocalEvidenceStore(settings.evidence_storage_path)
