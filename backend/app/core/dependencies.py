"""FastAPI dependency helpers."""

from __future__ import annotations

from fastapi import Request


async def get_container(request: Request):
    return request.app.state.container
