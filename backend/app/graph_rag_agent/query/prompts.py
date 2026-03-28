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
You are a query router for a story knowledge base that has two retrieval backends:
1. A **knowledge graph** (Neo4j) storing entities (characters, locations, objects, events) and their relationships.
2. A **vector store** (text chunks) containing the raw story passages.

Classify the user's latest question into exactly one retrieval type:

## "graph" — Use when the question:
- Asks about a specific named entity (character, place, object, event) — what happened to it, what it is, who it is
- Asks about relationships or connections between entities (e.g., who is related to whom, what connects X to Y)
- Requires multi-hop reasoning across entities (e.g., "How did character A affect event B?")
- Asks about an entity's role, status, fate, or attributes

## "vector" — Use when the question:
- Asks about themes, mood, tone, writing style, or narrative structure
- Requests a direct quote or specific wording from the text
- Asks about broad story summaries or overviews not tied to a specific entity
- Asks general "what happens in chapter X" style questions

## "hybrid" — Use when the question:
- Needs entity/relationship data AND supporting text passages for evidence
- Asks for detailed explanations that combine entity facts with narrative context
- Requires both structural (who/what/where) and textual (how/why described) information

## Examples:
- "What happened to the Obsidian Spire?" → "graph" (asking about a specific entity's fate)
- "Who are the main characters?" → "graph" (asking about character entities)
- "What is the relationship between Arthur and Elena?" → "graph" (relationship query)
- "How did Arthur Vance die?" → "graph" (specific entity event)
- "What is the overall tone of the story?" → "vector" (thematic, no specific entity)
- "Quote the passage where the Spire collapses" → "vector" (needs exact text)
- "Describe what happened at the Council meeting and why it mattered" → "hybrid" (entity event + narrative context)

## Decision Rule:
If the question mentions a specific named entity (person, place, thing, event), default to "graph" unless the question explicitly asks for a quote or theme.

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
    node_types: list[str],
    relationship_types: list[str],
    history_limit: int,
) -> list[BaseMessage]:
    nodes_str = ", ".join(node_types) if node_types else "Any (dynamically extracted)"
    rels_str = ", ".join(relationship_types) if relationship_types else "Any (dynamically extracted)"
    return [
        SystemMessage(
            content=f"""
Generate a Neo4j Cypher query to answer the user's latest story question.
All nodes have a story_id property. Always scope the query with story_id = $story_id.

Available node types in this story's graph: {nodes_str}
Available relationship types in this story's graph: {rels_str}
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
