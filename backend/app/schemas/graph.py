"""Graph payload models."""

from __future__ import annotations

from pydantic import BaseModel


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    description: str | None = None


class GraphEdge(BaseModel):
    source: str
    target: str
    relationship_type: str
    description: str | None = None


class GraphResponse(BaseModel):
    story_id: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]

