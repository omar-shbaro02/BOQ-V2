from functools import lru_cache
from pathlib import Path

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
    max_upload_bytes: int = 25 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
