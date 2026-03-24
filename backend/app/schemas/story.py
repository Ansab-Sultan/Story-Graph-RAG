"""Story, chat, ingestion, and retrieval evidence response models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import Citation
from app.schemas.graph import GraphEdge, GraphNode


class ChunkResult(BaseModel):
    chunk_id: str
    chunk_index: int | None = None
    text: str | None = None
    score: float | None = None


class GraphAnswerEvidence(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    relationships: list[GraphEdge] = Field(default_factory=list)
    raw_results: list[dict[str, object]] = Field(default_factory=list)


class QueryEvidence(BaseModel):
    graph: GraphAnswerEvidence | None = None
    chunk_ids: list[str] = Field(default_factory=list)
    chunks: list[ChunkResult] = Field(default_factory=list)


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


class StoryChunksResponse(BaseModel):
    story_id: str
    chunks: list[ChunkResult] = Field(default_factory=list)


class ChatSummary(BaseModel):
    chat_id: str
    story_id: str
    title: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
    turn_count: int = 0
    last_user_message: str | None = None
    last_answer_preview: str | None = None


class ChatMessage(BaseModel):
    message_id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime
    query_type: Literal["vector", "graph", "hybrid"] | None = None
    routing_reason: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    evidence: QueryEvidence | None = None


class ChatTranscriptResponse(BaseModel):
    story_id: str
    chat_id: str
    messages: list[ChatMessage] = Field(default_factory=list)


class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1)
    chat_id: str | None = Field(default=None, min_length=1)


class ChatMessageResponse(BaseModel):
    chat_id: str
    story_id: str
    created_new_chat: bool
    answer: str
    query_type: Literal["vector", "graph", "hybrid"]
    routing_reason: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    evidence: QueryEvidence | None = None
