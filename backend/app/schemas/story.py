"""Story, history, and ingestion response models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import Citation


class StoryResponse(BaseModel):
    story_id: str
    status: Literal["queued", "running", "complete", "error"]
    filename: str
    display_name: str


class StoryListItem(BaseModel):
    story_id: str
    title: str
    filename: str
    display_name: str
    status: str
    created_at: datetime | None = None
    entity_count: int | None = None
    relationship_count: int | None = None
    chunk_count: int | None = None


class QAHistoryItem(BaseModel):
    question: str
    answer: str
    query_type: str
    citations: list[Citation] = Field(default_factory=list)
    asked_at: datetime


class StoryDetail(BaseModel):
    story_id: str
    title: str
    filename: str
    display_name: str
    status: str
    created_at: datetime | None = None
    entity_count: int | None = None
    relationship_count: int | None = None
    chunk_count: int | None = None
    qa: list[QAHistoryItem] = Field(default_factory=list)

