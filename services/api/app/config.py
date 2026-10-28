from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VAI_", env_file=".env", extra="ignore")

    environment: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "postgresql+psycopg://vai:vai@localhost:5432/vai"
    cors_origins: list[str] = ["http://localhost:3000"]
    evidence_storage_backend: str = "local"
    evidence_storage_path: Path = Path(".data/evidence")
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    oidc_organization_claim: str = "https://vai.example/organization_id"
    oidc_principal_type_claim: str = "https://vai.example/principal_type"
    oidc_jwks_cache_seconds: int = Field(default=300, ge=30, le=3600)
    oidc_client_id: str | None = None
    oidc_client_secret: SecretStr | None = None
    oidc_authorization_url: str | None = None
    oidc_token_url: str | None = None
    session_public_origin: str | None = None
    session_encryption_keys: list[SecretStr] = Field(default_factory=list, max_length=3)
    session_max_age_seconds: int = Field(default=900, ge=60, le=3600)
    max_request_bytes: int = Field(default=64 * 1024 * 1024, ge=1024, le=128 * 1024 * 1024)
    rate_limit_per_minute: int = Field(default=120, ge=1, le=10000)
    adapter_timeout_seconds: float = Field(default=5, gt=0, le=30)
    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_endpoint_url: str | None = None
    s3_prefix: str = "vai/"
    s3_kms_key_id: str | None = None
    malware_scanner_backend: str = "development"
    clamd_host: str | None = None
    clamd_port: int = Field(default=3310, ge=1, le=65535)
    clamd_max_signature_age_hours: int = Field(default=48, ge=1, le=168)
    max_upload_bytes: int = Field(default=25 * 1024 * 1024, ge=1, le=64 * 1024 * 1024)
    max_artifact_bytes: int = Field(default=64 * 1024 * 1024, ge=1024, le=256 * 1024 * 1024)
    openai_api_key: SecretStr | None = None
    openai_schedule_model: str = "gpt-5"
    openai_agents_enabled: bool = True
    openai_agent_model: str = "gpt-5"
    openai_schedule_assistant_model: str = "gpt-5.6-sol"


@lru_cache
def get_settings() -> Settings:
    return Settings()
