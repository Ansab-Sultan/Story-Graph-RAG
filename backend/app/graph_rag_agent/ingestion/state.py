"""Typed state for the ingestion LangGraph workflow."""

from __future__ import annotations

from typing import Any, TypedDict


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

