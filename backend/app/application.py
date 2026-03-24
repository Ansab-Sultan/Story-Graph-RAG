"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Awaitable, Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.core.database import DatabaseManager
from app.core.exceptions import install_exception_handlers
from app.core.llm_config import LLMProviders, build_llm_providers
from app.core.logging import RequestContextMiddleware, setup_logging
from app.graph_rag_agent.ingestion.graph import compile_ingestion_graph
from app.graph_rag_agent.query.graph import compile_query_graph
from app.routers.health import router as health_router
from app.routers.query import router as query_router
from app.routers.stories import router as stories_router
from app.services.container import ServiceContainer, build_service_container


@dataclass(slots=True)
class AppContainer:
    settings: Settings
    database_manager: DatabaseManager
    llm_providers: LLMProviders
    services: ServiceContainer
    ingestion_graph: object
    query_graph: object


async def build_app_container(settings: Settings) -> AppContainer:
    database_manager = DatabaseManager(settings=settings)
    await database_manager.startup()

    llm_providers = build_llm_providers(settings)
    services = build_service_container(settings, database_manager, llm_providers)
    await services.story_service.ensure_indexes()
    await services.graph_service.ensure_indexes()

    return AppContainer(
        settings=settings,
        database_manager=database_manager,
        llm_providers=llm_providers,
        services=services,
        ingestion_graph=compile_ingestion_graph(services),
        query_graph=compile_query_graph(services),
    )


def create_app(
    *,
    settings: Settings | None = None,
    container_factory: Callable[[Settings], Awaitable[AppContainer]] | None = None,
) -> FastAPI:
    runtime_settings = settings or get_settings()
    setup_logging(runtime_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.container = await (container_factory or build_app_container)(runtime_settings)
        try:
            yield
        finally:
            await app.state.container.database_manager.shutdown()

    app = FastAPI(
        title=runtime_settings.app_name,
        debug=runtime_settings.debug,
        lifespan=lifespan,
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    install_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(stories_router)
    app.include_router(query_router)
    return app
