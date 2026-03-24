"""Application settings sourced from the environment."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import (
    DEFAULT_ALLOWED_NODE_TYPES,
    DEFAULT_ALLOWED_RELATIONSHIP_TYPES,
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_CORS_ORIGINS,
    DEFAULT_QUERY_TOP_K,
    DEFAULT_REDIS_LOCK_KEY,
    DEFAULT_SSE_POLL_INTERVAL_SECONDS,
    DEFAULT_UPLOAD_DIR,
)


class Settings(BaseSettings):
    """Single source of truth for local runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = Field(default="Story GraphRAG Backend", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=True, alias="DEBUG")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_chat_model: str = Field(default="gpt-4o-mini", alias="OPENAI_CHAT_MODEL")
    openai_embedding_model: str = Field(
        default="text-embedding-3-small",
        alias="OPENAI_EMBEDDING_MODEL",
    )

    neo4j_url: str = Field(default="bolt://localhost:7687", alias="NEO4J_URL")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_pass: str = Field(default="password", alias="NEO4J_PASS")
    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    redis_url: str = Field(default="redis://localhost:6379", alias="REDIS_URL")
    mongodb_url: str = Field(default="mongodb://localhost:27017", alias="MONGODB_URL")
    mongodb_db: str = Field(default="story_graphrag", alias="MONGODB_DB")

    upload_dir: Path = Field(default=Path(DEFAULT_UPLOAD_DIR), alias="UPLOAD_DIR")
    cors_origins: list[str] = Field(
        default_factory=lambda: list(DEFAULT_CORS_ORIGINS),
        alias="CORS_ORIGINS",
    )

    chunk_size: int = Field(default=DEFAULT_CHUNK_SIZE, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=DEFAULT_CHUNK_OVERLAP, alias="CHUNK_OVERLAP")
    query_top_k: int = Field(default=DEFAULT_QUERY_TOP_K, alias="QUERY_TOP_K")
    sse_poll_interval_seconds: float = Field(
        default=DEFAULT_SSE_POLL_INTERVAL_SECONDS,
        alias="SSE_POLL_INTERVAL_SECONDS",
    )
    ingestion_lock_key: str = Field(
        default=DEFAULT_REDIS_LOCK_KEY,
        alias="INGESTION_LOCK_KEY",
    )
    allowed_node_types: tuple[str, ...] = Field(
        default=DEFAULT_ALLOWED_NODE_TYPES,
        alias="ALLOWED_NODE_TYPES",
    )
    allowed_relationship_types: tuple[str, ...] = Field(
        default=DEFAULT_ALLOWED_RELATIONSHIP_TYPES,
        alias="ALLOWED_RELATIONSHIP_TYPES",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, value: str | list[str] | tuple[str, ...]) -> list[str]:
        if isinstance(value, (list, tuple)):
            return [item.strip() for item in value if item]
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return list(DEFAULT_CORS_ORIGINS)

    @field_validator("upload_dir", mode="before")
    @classmethod
    def _parse_upload_dir(cls, value: str | Path) -> Path:
        if isinstance(value, Path):
            return value
        return Path(value)

    @field_validator("debug", mode="before")
    @classmethod
    def _parse_debug(cls, value: bool | str) -> bool:
        if isinstance(value, bool):
            return value
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on", "debug"}:
            return True
        if normalized in {"0", "false", "no", "off", "release", "prod", "production"}:
            return False
        return bool(normalized)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()
