"""Chat metadata persistence helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import Settings
from app.core.exceptions import ChatNotFoundError
from app.schemas.story import ChatSummary


def _truncate_text(value: str, limit: int) -> str:
    normalized = " ".join(value.split()).strip()
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 1].rstrip()}…"


@dataclass(slots=True)
class ChatService:
    database: AsyncIOMotorDatabase
    settings: Settings

    @property
    def chats(self):
        return self.database["chats"]

    async def ensure_indexes(self) -> None:
        await self.chats.create_index([("story_id", 1), ("updated_at", -1)])
        await self.chats.create_index("thread_id", unique=True)

    async def create_chat(self, story_id: str, chat_id: str, first_message: str) -> ChatSummary:
        now = datetime.now(UTC)
        title = _truncate_text(first_message, self.settings.chat_title_max_length)
        doc = {
            "_id": chat_id,
            "chat_id": chat_id,
            "thread_id": chat_id,
            "story_id": story_id,
            "title": title,
            "created_at": now,
            "updated_at": now,
            "turn_count": 1,
            "last_user_message": _truncate_text(first_message, self.settings.chat_preview_max_length),
            "last_answer_preview": None,
        }
        await self.chats.insert_one(doc)
        return self._summary_from_doc(doc)

    async def update_chat_after_turn(
        self,
        story_id: str,
        chat_id: str,
        *,
        user_message: str,
        answer: str,
        turn_count: int,
    ) -> ChatSummary:
        now = datetime.now(UTC)
        await self.chats.update_one(
            {"_id": chat_id, "story_id": story_id},
            {
                "$set": {
                    "updated_at": now,
                    "turn_count": turn_count,
                    "last_user_message": _truncate_text(
                        user_message,
                        self.settings.chat_preview_max_length,
                    ),
                    "last_answer_preview": _truncate_text(
                        answer,
                        self.settings.chat_preview_max_length,
                    ),
                }
            },
        )
        return await self.get_chat(story_id, chat_id)

    async def list_story_chats(self, story_id: str) -> list[ChatSummary]:
        cursor = self.chats.find({"story_id": story_id}, sort=[("updated_at", -1)])
        items: list[ChatSummary] = []
        async for doc in cursor:
            items.append(self._summary_from_doc(doc))
        return items

    async def get_chat(self, story_id: str, chat_id: str) -> ChatSummary:
        doc = await self.chats.find_one({"_id": chat_id, "story_id": story_id})
        if doc is None:
            raise ChatNotFoundError(f"Chat '{chat_id}' was not found for story '{story_id}'.")
        return self._summary_from_doc(doc)

    def _summary_from_doc(self, doc: dict[str, object]) -> ChatSummary:
        return ChatSummary(
            chat_id=str(doc.get("_id") or doc["chat_id"]),
            story_id=str(doc["story_id"]),
            title=str(doc["title"]),
            created_at=doc.get("created_at"),
            updated_at=doc.get("updated_at"),
            turn_count=int(doc.get("turn_count", 0)),
            last_user_message=doc.get("last_user_message"),
            last_answer_preview=doc.get("last_answer_preview"),
        )
