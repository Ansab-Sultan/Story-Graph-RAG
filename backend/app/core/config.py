"""Application settings sourced from the environment."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.core.constants import (
    DEFAULT_CHAT_PREVIEW_MAX_LENGTH,
    DEFAULT_CHAT_PROMPT_HISTORY_MESSAGES,
    DEFAULT_CHAT_TITLE_MAX_LENGTH,
    DEFAULT_CHECKPOINT_COLLECTION_NAME,
    DEFAULT_CHECKPOINT_WRITES_COLLECTION_NAME,
    DEFAULT_CORS_ORIGINS,
    DEFAULT_GRAPH_CHUNK_OVERLAP,
    DEFAULT_GRAPH_CHUNK_SIZE,
    DEFAULT_INFRASTRUCTURE_TIMEOUT_SECONDS,
    DEFAULT_QUERY_TOP_K,
    DEFAULT_REDIS_LOCK_KEY,
    DEFAULT_SSE_POLL_INTERVAL_SECONDS,
    DEFAULT_UPLOAD_DIR,
    DEFAULT_VECTOR_CHUNK_OVERLAP,
    DEFAULT_VECTOR_CHUNK_SIZE,
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
    third_party_log_level: str = Field(
        default="WARNING",
        alias="THIRD_PARTY_LOG_LEVEL",
    )
    verbose_external_logs: bool = Field(
        default=False,
        alias="VERBOSE_EXTERNAL_LOGS",
    )

    # --- Gemini (commented out) ---
    # google_api_key: str | None = Field(default=None, alias="GOOGLE_API_KEY")
    # google_chat_model: str = Field(
    #     default="gemini-3.1-flash-lite-preview",
    #     alias="GOOGLE_CHAT_MODEL",
    # )

    # --- Mistral ---
    mistral_api_key: str | None = Field(default=None, alias="MISTRAL_API_KEY")
    mistral_model: str = Field(
        default="mistral-large-latest",
        alias="MISTRAL_MODEL",
    )
    embedding_model: str = Field(
        default="BAAI/bge-small-en-v1.5",
        alias="EMBEDDING_MODEL",
    )
    embedding_device: str = Field(default="cpu", alias="EMBEDDING_DEVICE")
    embedding_normalize: bool = Field(default=True, alias="EMBEDDING_NORMALIZE")

    neo4j_url: str = Field(default="bolt://localhost:7687", alias="NEO4J_URL")
    neo4j_user: str = Field(default="neo4j", alias="NEO4J_USER")
    neo4j_pass: str = Field(default="password", alias="NEO4J_PASS")
    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    redis_url: str = Field(default="redis://localhost:6379", alias="REDIS_URL")
    mongodb_url: str = Field(default="mongodb://localhost:27017", alias="MONGODB_URL")
    mongodb_db: str = Field(default="story_graphrag", alias="MONGODB_DB")
    checkpoint_db: str | None = Field(default=None, alias="CHECKPOINT_DB")
    checkpoint_collection_name: str = Field(
        default=DEFAULT_CHECKPOINT_COLLECTION_NAME,
        alias="CHECKPOINT_COLLECTION_NAME",
    )
    checkpoint_writes_collection_name: str = Field(
        default=DEFAULT_CHECKPOINT_WRITES_COLLECTION_NAME,
        alias="CHECKPOINT_WRITES_COLLECTION_NAME",
    )

    upload_dir: Path = Field(default=Path(DEFAULT_UPLOAD_DIR), alias="UPLOAD_DIR")
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: list(DEFAULT_CORS_ORIGINS),
        alias="CORS_ORIGINS",
    )

    vector_chunk_size: int | None = Field(default=None, alias="VECTOR_CHUNK_SIZE")
    vector_chunk_overlap: int | None = Field(default=None, alias="VECTOR_CHUNK_OVERLAP")
    graph_chunk_size: int = Field(default=DEFAULT_GRAPH_CHUNK_SIZE, alias="GRAPH_CHUNK_SIZE")
    graph_chunk_overlap: int = Field(default=DEFAULT_GRAPH_CHUNK_OVERLAP, alias="GRAPH_CHUNK_OVERLAP")
    legacy_chunk_size: int | None = Field(default=None, alias="CHUNK_SIZE", exclude=True, repr=False)
    legacy_chunk_overlap: int | None = Field(
        default=None,
        alias="CHUNK_OVERLAP",
        exclude=True,
        repr=False,
    )
    query_top_k: int = Field(default=DEFAULT_QUERY_TOP_K, alias="QUERY_TOP_K")
    sse_poll_interval_seconds: float = Field(
        default=DEFAULT_SSE_POLL_INTERVAL_SECONDS,
        alias="SSE_POLL_INTERVAL_SECONDS",
    )
    ingestion_lock_key: str = Field(
        default=DEFAULT_REDIS_LOCK_KEY,
        alias="INGESTION_LOCK_KEY",
    )
    chat_title_max_length: int = Field(
        default=DEFAULT_CHAT_TITLE_MAX_LENGTH,
        alias="CHAT_TITLE_MAX_LENGTH",
    )
    chat_preview_max_length: int = Field(
        default=DEFAULT_CHAT_PREVIEW_MAX_LENGTH,
        alias="CHAT_PREVIEW_MAX_LENGTH",
    )
    chat_prompt_history_messages: int = Field(
        default=DEFAULT_CHAT_PROMPT_HISTORY_MESSAGES,
        alias="CHAT_PROMPT_HISTORY_MESSAGES",
    )
    infrastructure_timeout_seconds: float = Field(
        default=DEFAULT_INFRASTRUCTURE_TIMEOUT_SECONDS,
        alias="INFRASTRUCTURE_TIMEOUT_SECONDS",
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

    @field_validator("embedding_normalize", mode="before")
    @classmethod
    def _parse_embedding_normalize(cls, value: bool | str) -> bool:
        if isinstance(value, bool):
            return value
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        return bool(normalized)

    @field_validator("verbose_external_logs", mode="before")
    @classmethod
    def _parse_verbose_external_logs(cls, value: bool | str) -> bool:
        if isinstance(value, bool):
            return value
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        return bool(normalized)

    @model_validator(mode="after")
    def _finalize_chunk_settings(self) -> "Settings":
        if self.vector_chunk_size is None:
            self.vector_chunk_size = self.legacy_chunk_size or DEFAULT_VECTOR_CHUNK_SIZE
        if self.vector_chunk_overlap is None:
            self.vector_chunk_overlap = self.legacy_chunk_overlap or DEFAULT_VECTOR_CHUNK_OVERLAP

        self._validate_chunk_pair(
            "vector_chunk_size",
            self.vector_chunk_size,
            "vector_chunk_overlap",
            self.vector_chunk_overlap,
        )
        self._validate_chunk_pair(
            "graph_chunk_size",
            self.graph_chunk_size,
            "graph_chunk_overlap",
            self.graph_chunk_overlap,
        )
        return self

    @staticmethod
    def _validate_chunk_pair(
        size_name: str,
        size: int,
        overlap_name: str,
        overlap: int,
    ) -> None:
        if size <= 0:
            raise ValueError(f"{size_name} must be greater than 0.")
        if overlap < 0:
            raise ValueError(f"{overlap_name} must be greater than or equal to 0.")
        if overlap >= size:
            raise ValueError(f"{overlap_name} must be smaller than {size_name}.")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings instance."""

    return Settings()
