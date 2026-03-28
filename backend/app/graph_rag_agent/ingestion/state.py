"""Typed state for the ingestion LangGraph workflow."""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict


class IngestionState(TypedDict):
    story_id: str
    title: str
    file_path: str
    raw_text: str
    graph_chunks: list[Any]
    vector_chunks: list[Any]
    graph_docs: list[Any]
    alias_map: dict[str, str]
    graph_built: bool
    vectors_stored: bool
    progress: Annotated[list[str], add]
