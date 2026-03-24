"""Shared API models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    detail: str
    error_code: str


class Citation(BaseModel):
    type: Literal["chunk", "graph_node", "graph_edge"]
    reference: str
    excerpt: str | None = None


class ProgressEvent(BaseModel):
    node: str
    progress: str
    status: str | None = None


class HealthResponse(BaseModel):
    status: str
    services: dict[str, str] = Field(default_factory=dict)

