"""Typed workflow state and structured helper models."""

from __future__ import annotations

from typing import Any, TypedDict

from pydantic import BaseModel, Field


class DuplicateGroup(BaseModel):
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)


class DeduplicationOutput(BaseModel):
    groups: list[DuplicateGroup] = Field(default_factory=list)


class IngestionState(TypedDict):
    story_id: str
    title: str
    file_path: str
    raw_text: str
    chunks: list[Any]
    graph_docs: list[Any]
    alias_map: dict[str, str]
    graph_built: bool
    vectors_stored: bool
    progress: list[str]


class QueryState(TypedDict):
    story_id: str
    question: str
    query_type: str
    cypher_query: str | None
    graph_results: list[dict[str, Any]] | None
    vector_results: list[dict[str, Any]] | None
    answer: str
    citations: list[dict[str, Any]]
