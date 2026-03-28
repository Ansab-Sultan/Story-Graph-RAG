"""Persistence helpers for story metadata."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.exceptions import StoryNotFoundError
from app.schemas.story import StoryDetail, StoryListItem


@dataclass(slots=True)
class StoryService:
    database: AsyncIOMotorDatabase

    @property
    def stories(self):
        return self.database["stories"]

    async def ensure_indexes(self) -> None:
        await self.stories.create_index("filename", unique=True)
        await self.stories.create_index("created_at")

    async def filename_exists(self, filename: str) -> bool:
        return await self.stories.count_documents({"filename": filename}, limit=1) > 0

    async def create_story_record(
        self,
        story_id: str,
        filename: str,
        *,
        status: str = "queued",
    ) -> None:
        now = datetime.now(UTC)
        await self.stories.insert_one(
            {
                "_id": story_id,
                "title": filename,
                "filename": filename,
                "display_name": filename,
                "status": status,
                "entity_count": 0,
                "relationship_count": 0,
                "chunk_count": 0,
                "created_at": now,
            }
        )

    async def update_story_status(self, story_id: str, status: str, *, error: str | None = None) -> None:
        payload: dict[str, object] = {"status": status}
        if error is not None:
            payload["error"] = error
        await self.stories.update_one({"_id": story_id}, {"$set": payload})

    async def complete_story(
        self,
        story_id: str,
        *,
        title: str,
        entity_count: int,
        relationship_count: int,
        chunk_count: int,
    ) -> None:
        await self.stories.update_one(
            {"_id": story_id},
            {
                "$set": {
                    "title": title,
                    "display_name": title,
                    "status": "complete",
                    "entity_count": entity_count,
                    "relationship_count": relationship_count,
                    "chunk_count": chunk_count,
                    "completed_at": datetime.now(UTC),
                }
            },
        )

    async def list_stories(self) -> list[StoryListItem]:
        cursor = self.stories.find({}, sort=[("created_at", -1)])
        items: list[StoryListItem] = []
        async for doc in cursor:
            items.append(
                StoryListItem(
                    story_id=str(doc["_id"]),
                    title=doc.get("title", doc.get("filename", "")),
                    filename=doc.get("filename", ""),
                    display_name=doc.get("display_name", doc.get("filename", "")),
                    status=doc.get("status", "queued"),
                    created_at=doc.get("created_at"),
                    entity_count=doc.get("entity_count"),
                    relationship_count=doc.get("relationship_count"),
                    chunk_count=doc.get("chunk_count"),
                )
            )
        return items

    async def get_story_detail(self, story_id: str) -> StoryDetail:
        doc = await self.stories.find_one({"_id": story_id})
        if doc is None:
            raise StoryNotFoundError(f"Story '{story_id}' was not found.")

        return StoryDetail(
            story_id=str(doc["_id"]),
            title=doc.get("title", doc.get("filename", "")),
            filename=doc.get("filename", ""),
            display_name=doc.get("display_name", doc.get("filename", "")),
            status=doc.get("status", "queued"),
            created_at=doc.get("created_at"),
            entity_count=doc.get("entity_count"),
            relationship_count=doc.get("relationship_count"),
            chunk_count=doc.get("chunk_count"),
        )

    async def delete_story(self, story_id: str) -> None:
        await self.stories.delete_one({"_id": story_id})
