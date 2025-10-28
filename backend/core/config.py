"""Application settings and configuration helpers."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed configuration sourced from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    app_name: str = Field(default="ZUS AI Assistant", description="Human-readable service name.")
    environment: str = Field(default="local", description="Deployment environment identifier.")

    openai_api_key: str | None = Field(default=None, description="Optional OpenAI API key.")
    embedding_model: str = Field(default="text-embedding-3-large", description="Embedding model name.")

    sqlite_path: Path = Field(default=Path("../db/conversations.db"), description="Conversation DB path.")
    outlets_db_path: Path = Field(default=Path("../db/outlets.db"), description="Outlet DB file path.")
    faiss_index_path: Path = Field(
        default=Path("../db/faiss/products.index"), description="FAISS index file location."
    )
    products_metadata_path: Path = Field(
        default=Path("../db/faiss/products_metadata.json"),
        description="Path to cached drinkware metadata for retrieval responses.",
    )

    calculator_timeout_ms: int = Field(default=2000, ge=100, description="Calculator evaluation timeout.")
    log_level: str = Field(default="INFO", description="Application log level.")

    frontend_origin: AnyHttpUrl | None = Field(
        default=None,
        description="Allowed frontend origin (CORS). If omitted, defaults to localhost dev server.",
    )
    additional_origins: List[AnyHttpUrl] = Field(
        default_factory=list,
        description="Additional allowed CORS origins for multi-client deployments.",
    )

    @property
    def cors_origins(self) -> list[str]:
        """Return the full list of allowed CORS origins."""

        origins: list[str] = []
        if self.frontend_origin:
            origins.append(str(self.frontend_origin))
        else:
            origins.append("http://localhost:5173")
        origins.extend(str(origin) for origin in self.additional_origins)
        return origins


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings instance."""

    return Settings()
