"""Prompt builders for query workflow."""

from __future__ import annotations

import json


def build_router_prompt(question: str) -> str:
    return f"""
Classify this question about a story into one of three retrieval types:

- "vector": factual, descriptive, or thematic questions answerable from text passages
- "graph": questions about relationships, connections, or multi-hop reasoning between characters/events
- "hybrid": questions that require both text passages AND relationship traversal

Question: {question}
""".strip()


def build_cypher_prompt(
    *,
    story_id: str,
    question: str,
    allowed_relationships: tuple[str, ...],
) -> str:
    relationships = ", ".join(allowed_relationships)
    return f"""
Generate a Neo4j Cypher query to answer the following question.
All nodes have a story_id property. Always scope the query with story_id = $story_id.

Available node types: CHARACTER, PLACE, EVENT, OBJECT, THEME
Available relationship types: {relationships}
Return results in a readable shape for answer synthesis.

Question: {question}
Story ID: {story_id}
""".strip()


def build_answer_prompt(
    *,
    question: str,
    query_type: str,
    graph_results: list[dict] | None,
    vector_results: list[dict] | None,
) -> str:
    graph_payload = json.dumps(graph_results or [], default=str)
    vector_payload = json.dumps(vector_results or [], default=str)
    return f"""
Answer the user's story question using only the evidence provided.
Return a concise answer and cite the exact chunks or graph relationships used.

Question: {question}
Query type: {query_type}
Graph results: {graph_payload}
Vector results: {vector_payload}
""".strip()

