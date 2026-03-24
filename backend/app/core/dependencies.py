"""FastAPI dependency helpers."""

from __future__ import annotations

from fastapi import Request

from app.core.config import Settings, get_settings


def get_settings_dependency() -> Settings:
    return get_settings()


def get_container(request: Request):
    return request.app.state.container

