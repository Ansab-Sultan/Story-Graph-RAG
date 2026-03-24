"""Story upload, progress, graph, and history routes."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Request, UploadFile
from fastapi.responses import StreamingResponse

from app.core.dependencies import get_container
from app.core.exceptions import ActiveIngestionError, DuplicateFilenameError, StoryNotFoundError
from app.core.logging import get_logger
from app.schemas.graph import GraphResponse
from app.schemas.story import QAHistoryItem, StoryDetail, StoryListItem, StoryResponse

logger = get_logger(__name__)
router = APIRouter(prefix="/api/stories", tags=["stories"])


def _sse_message(event: str, payload: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"


async def _run_ingestion_job(
    container,
    *,
    story_id: str,
    title: str,
    file_path: str,
) -> None:
    services = container.services
    initial_state = {
        "story_id": story_id,
        "title": title,
        "file_path": file_path,
        "raw_text": "",
        "chunks": [],
        "graph_docs": [],
        "alias_map": {},
        "graph_built": False,
        "vectors_stored": False,
        "progress": [],
    }

    try:
        await services.story_service.update_story_status(story_id, "running")
        await services.job_service.set_job_status(story_id, "running")

        async for update in container.ingestion_graph.astream(
            initial_state,
            stream_mode="updates",
        ):
            node_name = next(iter(update))
            node_output = update[node_name]
            progress = (node_output.get("progress") or [""])[-1]
            await services.job_service.append_progress(
                story_id,
                node=node_name,
                progress=progress,
                status="running",
            )

        entity_count, relationship_count = await services.graph_service.get_story_counts(story_id)
        chunk_count = await services.vector_service.count_points(story_id)
        await services.story_service.complete_story(
            story_id,
            title=title,
            entity_count=entity_count,
            relationship_count=relationship_count,
            chunk_count=chunk_count,
        )
        await services.job_service.set_job_status(story_id, "complete")
        await services.job_service.append_progress(
            story_id,
            node="complete",
            progress="✓ Story ready",
            status="complete",
        )
    except Exception as exc:
        logger.exception("Ingestion failed for story %s: %s", story_id, exc)
        await services.story_service.update_story_status(story_id, "error", error=str(exc))
        await services.job_service.set_job_status(story_id, "error", error=str(exc))
        await services.job_service.append_progress(
            story_id,
            node="error",
            progress=str(exc),
            status="error",
        )
    finally:
        await services.job_service.release_ingestion_lock(story_id)
        services.file_service.cleanup(file_path)


@router.post("", response_model=StoryResponse)
async def upload_story(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    container=Depends(get_container),
) -> StoryResponse:
    filename = file.filename or ""
    if await container.services.story_service.filename_exists(filename):
        raise DuplicateFilenameError(f"A story named '{filename}' already exists.")

    story_id = str(uuid4())
    lock_acquired = await container.services.job_service.acquire_ingestion_lock(story_id)
    if not lock_acquired:
        raise ActiveIngestionError("Another story is currently being ingested.")

    try:
        file_path = await container.services.file_service.save_upload(file, story_id)
        await container.services.story_service.create_story_record(
            story_id,
            filename=filename,
            status="queued",
        )
        await container.services.job_service.initialize_job(story_id, filename)
        background_tasks.add_task(
            _run_ingestion_job,
            container,
            story_id=story_id,
            title=filename,
            file_path=str(file_path),
        )
    except Exception:
        await container.services.job_service.release_ingestion_lock(story_id)
        raise

    return StoryResponse(
        story_id=story_id,
        status="queued",
        filename=filename,
        display_name=filename,
    )


@router.get("", response_model=list[StoryListItem])
async def list_stories(container=Depends(get_container)) -> list[StoryListItem]:
    return await container.services.story_service.list_stories()


@router.get("/{story_id}", response_model=StoryDetail)
async def get_story_detail(story_id: str, container=Depends(get_container)) -> StoryDetail:
    return await container.services.story_service.get_story_detail(story_id)


@router.get("/{story_id}/qa", response_model=list[QAHistoryItem])
async def get_story_qa_history(
    story_id: str,
    container=Depends(get_container),
) -> list[QAHistoryItem]:
    return await container.services.story_service.get_qa_history(story_id)


@router.get("/{story_id}/graph", response_model=GraphResponse)
async def get_story_graph(story_id: str, container=Depends(get_container)) -> GraphResponse:
    await container.services.story_service.get_story_detail(story_id)
    return await container.services.graph_service.fetch_story_graph(story_id)


@router.get("/{story_id}/stream")
async def stream_story_progress(
    story_id: str,
    request: Request,
    container=Depends(get_container),
) -> StreamingResponse:
    job_status = await container.services.job_service.get_job_status(story_id)
    if not job_status:
        detail = None
        try:
            detail = await container.services.story_service.get_story_detail(story_id)
        except StoryNotFoundError:
            detail = None
        if detail is None:
            raise StoryNotFoundError(f"Story '{story_id}' was not found.")

    async def event_generator():
        index = 0
        while not await request.is_disconnected():
            events, index = await container.services.job_service.read_progress_since(story_id, index)
            for event in events:
                yield _sse_message("progress", event.model_dump())

            job = await container.services.job_service.get_job_status(story_id)
            status = job.get("status")
            if status in {"complete", "error"}:
                yield _sse_message(status, job)
                break

            await asyncio.sleep(container.settings.sse_poll_interval_seconds)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
