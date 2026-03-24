"""Query API and structured output models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.common import Citation


class QueryRequest(BaseModel):
    question: str = Field(min_length=1)


class QueryResponse(BaseModel):
    answer: str
    query_type: Literal["vector", "graph", "hybrid"]
    citations: list[Citation] = Field(default_factory=list)


class RouterOutput(BaseModel):
    query_type: Literal["vector", "graph", "hybrid"]
    reasoning: str


class CypherOutput(BaseModel):
    cypher: str


class AnswerOutput(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)

