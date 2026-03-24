"""Query workflow structured output models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import Citation


class RouterOutput(BaseModel):
    query_type: Literal["vector", "graph", "hybrid"]
    reasoning: str


class CypherOutput(BaseModel):
    cypher: str


class AnswerOutput(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
