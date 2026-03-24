"""Redis-backed ingestion job state and progress streaming."""

from __future__ import annotations

from dataclasses import dataclass
import json

import redis.asyncio as redis_async

from app.core.config import Settings
from app.schemas.common import ProgressEvent


@dataclass(slots=True)
class JobStateService:
    redis: redis_async.Redis
    settings: Settings

    def _job_key(self, story_id: str) -> str:
        return f"story-graphrag:job:{story_id}"

    def _stream_key(self, story_id: str) -> str:
        return f"story-graphrag:stream:{story_id}"

    async def acquire_ingestion_lock(self, story_id: str) -> bool:
        return bool(
            await self.redis.set(
                self.settings.ingestion_lock_key,
                story_id,
                nx=True,
            )
        )

    async def release_ingestion_lock(self, story_id: str | None = None) -> None:
        lock_owner = await self.redis.get(self.settings.ingestion_lock_key)
        if story_id is None or lock_owner == story_id:
            await self.redis.delete(self.settings.ingestion_lock_key)

    async def has_active_ingestion(self) -> bool:
        return await self.redis.exists(self.settings.ingestion_lock_key) == 1

    async def initialize_job(self, story_id: str, filename: str) -> None:
        await self.redis.hset(
            self._job_key(story_id),
            mapping={
                "status": "queued",
                "filename": filename,
            },
        )

    async def set_job_status(self, story_id: str, status: str, *, error: str | None = None) -> None:
        mapping: dict[str, str] = {"status": status}
        if error is not None:
            mapping["error"] = error
        await self.redis.hset(self._job_key(story_id), mapping=mapping)

    async def get_job_status(self, story_id: str) -> dict[str, str]:
        return await self.redis.hgetall(self._job_key(story_id))

    async def append_progress(
        self,
        story_id: str,
        *,
        node: str,
        progress: str,
        status: str | None = None,
    ) -> None:
        payload = ProgressEvent(node=node, progress=progress, status=status).model_dump()
        await self.redis.rpush(self._stream_key(story_id), json.dumps(payload))

    async def read_progress_since(self, story_id: str, index: int) -> tuple[list[ProgressEvent], int]:
        values = await self.redis.lrange(self._stream_key(story_id), index, -1)
        events = [ProgressEvent.model_validate_json(value) for value in values]
        return events, index + len(events)

