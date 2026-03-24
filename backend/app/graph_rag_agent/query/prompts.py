"""Prompt builders for query workflow."""

from __future__ import annotations

import json
from collections.abc import Sequence

from langchain_core.messages import BaseMessage, SystemMessage


def _recent_messages(
    messages: Sequence[BaseMessage] | None,
    limit: int,
) -> list[BaseMessage]:
    if not messages:
        return []
    return list(messages[-limit:])


def build_router_prompt(*, messages: Sequence[BaseMessage], history_limit: int) -> list[BaseMessage]:
    return [
        SystemMessage(
            content="""
Classify the user's latest story question into one of three retrieval types:

- "vector": factual, descriptive, or thematic questions answerable from text passages
- "graph": questions about relationships, connections, or multi-hop reasoning between characters/events
- "hybrid": questions that require both text passages and relationship traversal

Use the recent conversation history to resolve follow-up references like pronouns or ellipsis.
Return only the structured classification.
""".strip()
        ),
        *_recent_messages(messages, history_limit),
    ]


def build_cypher_prompt(
    *,
    story_id: str,
    messages: Sequence[BaseMessage],
    allowed_relationships: tuple[str, ...],
    history_limit: int,
) -> list[BaseMessage]:
    relationships = ", ".join(allowed_relationships)
    return [
        SystemMessage(
            content=f"""
Generate a Neo4j Cypher query to answer the user's latest story question.
All nodes have a story_id property. Always scope the query with story_id = $story_id.

Available node types: CHARACTER, PLACE, EVENT, OBJECT, THEME
Available relationship types: {relationships}
Return results in a readable shape for answer synthesis.

Story ID: {story_id}
Use the recent conversation history to resolve follow-up references when needed.
Return only the structured Cypher output.
""".strip()
        ),
        *_recent_messages(messages, history_limit),
    ]


def build_answer_prompt(
    *,
    query_type: str,
    graph_results: list[dict] | None,
    vector_results: list[dict] | None,
    messages: Sequence[BaseMessage],
    history_limit: int,
) -> list[BaseMessage]:
    graph_payload = json.dumps(graph_results or [], default=str)
    vector_payload = json.dumps(vector_results or [], default=str)
    return [
        SystemMessage(
            content=f"""
Answer the user's latest story question using only the evidence provided.
Return a concise answer and cite the exact chunks or graph relationships used.

Query type: {query_type}
Graph results: {graph_payload}
Vector results: {vector_payload}
Use the recent conversation history to resolve follow-up references, but do not invent facts that
are not supported by the current graph or vector evidence.
Return only the structured answer output.
""".strip()
        ),
        *_recent_messages(messages, history_limit),
    ]
