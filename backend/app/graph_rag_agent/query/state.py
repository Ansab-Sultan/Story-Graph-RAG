"""Typed state for the query LangGraph workflow."""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class QueryState(TypedDict):
    story_id: str
    question: str
    messages: Annotated[list[BaseMessage], add_messages]
    transcript: Annotated[list[dict[str, Any]], add]
    query_type: str
    routing_reason: str | None
    cypher_query: str | None
    graph_results: list[dict[str, Any]] | None
    vector_results: list[dict[str, Any]] | None
    evidence: dict[str, Any] | None
    answer: str
    citations: list[dict[str, Any]]
