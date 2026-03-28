"""ASGI entrypoint and application factory for the Story GraphRAG backend."""

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
from app.routers.stories import router as stories_router
from app.services.container import ServiceContainer, build_service_container
from create_index import create_indexes


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

    container = AppContainer(
        settings=settings,
        database_manager=database_manager,
        llm_providers=llm_providers,
        services=services,
        ingestion_graph=compile_ingestion_graph(services),
        query_graph=compile_query_graph(
            services,
            checkpointer=database_manager.mongo_checkpointer,
        ),
    )
    await create_indexes(container)
    return container


def create_app(
    *,
    settings: Settings | None = None,
    container_factory: Callable[[Settings], Awaitable[AppContainer]] | None = None,
) -> FastAPI:
    runtime_settings = settings or get_settings()
    setup_logging(
        level=runtime_settings.log_level,
        third_party_level=runtime_settings.third_party_log_level,
        verbose_third_party=runtime_settings.verbose_external_logs,
    )

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
        swagger_ui_parameters={
            "defaultModelsExpandDepth": -1,
            "persistAuthorization": True,
            "displayRequestDuration": True,
            "filter": True,
        }
    )

    # Injected CSS for Cinematic Tech Theme
    brand_css = """
    .swagger-ui { background-color: #020203; color: #EDEDEF; }
    .swagger-ui .topbar { background-color: #0A0A0F; border-bottom: 1px solid rgba(255,255,255,0.1); padding: 10px 0; }
    .swagger-ui .info .title { color: #0052FF; font-family: 'Inter', sans-serif; font-weight: 800; letter-spacing: -0.02em; }
    .swagger-ui .opblock.opblock-get { background: rgba(0, 82, 255, 0.05); border-color: rgba(0, 82, 255, 0.2); }
    .swagger-ui .opblock.opblock-post { background: rgba(139, 0, 255, 0.05); border-color: rgba(139, 0, 255, 0.2); }
    .swagger-ui section.models { border: 1px solid rgba(255,255,255,0.05); border-radius: 12px; background: rgba(255,255,255,0.02); }
    .swagger-ui .btn.authorize { color: #0052FF; border-color: #0052FF; background: transparent; border-radius: 8px; }
    .swagger-ui .btn.authorize svg { fill: #0052FF; }
    .swagger-ui .btn.authorize:hover { background: rgba(0, 82, 255, 0.1); }
    """

    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        from fastapi.openapi.docs import get_swagger_ui_html
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=app.title + " - API Docs",
            oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
            swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
            swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
            swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
        )

    @app.get("/docs/theme.css", include_in_schema=False)
    async def get_theme_css():
        from fastapi.responses import Response
        return Response(content=brand_css, media_type="text/css")
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.cors_origins,
        allow_credentials=runtime_settings.cors_origins != ["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    install_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(stories_router)
    return app


app = create_app()
