"""ASGI entrypoint for the Story GraphRAG backend."""

from app.application import create_app

app = create_app()

