"""Database client lifecycle management."""

from __future__ import annotations

from dataclasses import dataclass

import redis.asyncio as redis_async
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from neo4j import AsyncDriver, AsyncGraphDatabase
from qdrant_client import AsyncQdrantClient

from app.core.config import Settings


@dataclass(slots=True)
class DatabaseManager:
    settings: Settings
    mongo_client: AsyncIOMotorClient | None = None
    mongo_db: AsyncIOMotorDatabase | None = None
    redis: redis_async.Redis | None = None
    qdrant: AsyncQdrantClient | None = None
    neo4j: AsyncDriver | None = None

    async def startup(self) -> None:
        self.settings.upload_dir.mkdir(parents=True, exist_ok=True)
        self.mongo_client = AsyncIOMotorClient(self.settings.mongodb_url)
        self.mongo_db = self.mongo_client[self.settings.mongodb_db]
        self.redis = redis_async.from_url(self.settings.redis_url, decode_responses=True)
        self.qdrant = AsyncQdrantClient(url=self.settings.qdrant_url)
        self.neo4j = AsyncGraphDatabase.driver(
            self.settings.neo4j_url,
            auth=(self.settings.neo4j_user, self.settings.neo4j_pass),
        )

    async def shutdown(self) -> None:
        if self.redis is not None:
            await self.redis.aclose()
        if self.qdrant is not None:
            await self.qdrant.close()
        if self.neo4j is not None:
            await self.neo4j.close()
        if self.mongo_client is not None:
            self.mongo_client.close()

    async def ping(self) -> dict[str, str]:
        status: dict[str, str] = {}

        try:
            assert self.mongo_db is not None
            await self.mongo_db.command("ping")
            status["mongo"] = "ok"
        except Exception:
            status["mongo"] = "unavailable"

        try:
            assert self.redis is not None
            await self.redis.ping()
            status["redis"] = "ok"
        except Exception:
            status["redis"] = "unavailable"

        try:
            assert self.qdrant is not None
            await self.qdrant.get_collections()
            status["qdrant"] = "ok"
        except Exception:
            status["qdrant"] = "unavailable"

        try:
            assert self.neo4j is not None
            await self.neo4j.verify_connectivity()
            status["neo4j"] = "ok"
        except Exception:
            status["neo4j"] = "unavailable"

        return status
