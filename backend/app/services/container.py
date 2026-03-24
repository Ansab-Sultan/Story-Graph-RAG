"""Service bundle assembly."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.config import Settings
from app.core.database import DatabaseManager
from app.core.llm_config import LLMProviders
from app.services.chat_service import ChatService
from app.services.file_service import FileService
from app.services.graph_service import GraphService
from app.services.job_service import JobStateService
from app.services.story_service import StoryService
from app.services.vector_service import VectorService


@dataclass(slots=True)
class ServiceContainer:
    settings: Settings
    file_service: FileService
    story_service: StoryService
    chat_service: ChatService
    job_service: JobStateService
    graph_service: GraphService
    vector_service: VectorService
    llm_providers: LLMProviders


def build_service_container(
    settings: Settings,
    database_manager: DatabaseManager,
    llm_providers: LLMProviders,
) -> ServiceContainer:
    assert database_manager.mongo_db is not None
    assert database_manager.redis is not None
    assert database_manager.neo4j is not None
    assert database_manager.qdrant is not None

    return ServiceContainer(
        settings=settings,
        file_service=FileService(settings=settings),
        story_service=StoryService(database=database_manager.mongo_db),
        chat_service=ChatService(database=database_manager.mongo_db, settings=settings),
        job_service=JobStateService(redis=database_manager.redis, settings=settings),
        graph_service=GraphService(driver=database_manager.neo4j, settings=settings),
        vector_service=VectorService(
            client=database_manager.qdrant,
            embeddings=llm_providers.embeddings,
            settings=settings,
        ),
        llm_providers=llm_providers,
    )
