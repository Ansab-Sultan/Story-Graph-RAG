"""Startup index creation helpers."""

from __future__ import annotations


async def create_indexes(container) -> None:
    """Create database indexes required by the application at startup."""

    await container.services.story_service.ensure_indexes()
    await container.services.chat_service.ensure_indexes()
    await container.services.graph_service.ensure_indexes()
