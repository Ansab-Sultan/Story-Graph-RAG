"""Story upload, progress, graph, chat, and history routes."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, Request, UploadFile
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage

from app.core.dependencies import get_container
from app.core.exceptions import (
    ActiveIngestionError,
    DuplicateFilenameError,
    StoryNotFoundError,
    StoryNotReadyError,
)
from app.core.logging import get_logger
from app.schemas.graph import GraphResponse
from app.schemas.story import (
    ChatMessage,
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSummary,
    ChatTranscriptResponse,
    StoryChunksResponse,
    StoryDetail,
    StoryListItem,
    StoryResponse,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/stories", tags=["stories"])
_INGESTION_STAGE_LABELS = {
    "queued": "Queued",
    "loader": "Preparing Document",
    "graph_extractor": "Extracting Graph",
    "gleaning": "Gleaning Details",
    "deduplication": "Deduplicating Entities",
    "graph_builder": "Writing Neo4j Graph",
    "vector_embedder": "Embedding for Qdrant",
    "complete": "Story Ready",
    "error": "Failed",
}
_INGESTION_TOTAL_STEPS = 6


def _sse_message(event: str, payload: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"


def _build_user_transcript(message: str, message_id: str) -> dict[str, object]:
    return {
        "message_id": message_id,
        "role": "user",
        "content": message,
        "created_at": datetime.now(UTC).isoformat(),
    }


def _count_turns(transcript: list[dict[str, object]] | None) -> int:
    if not transcript:
        return 0
    return sum(1 for item in transcript if item.get("role") == "assistant")


def _build_progress_metadata(node: str, completed_steps: int) -> dict[str, int | str]:
    bounded_steps = max(0, min(completed_steps, _INGESTION_TOTAL_STEPS))
    return {
        "stage": _INGESTION_STAGE_LABELS.get(node, node.replace("_", " ").title()),
        "step": bounded_steps,
        "total_steps": _INGESTION_TOTAL_STEPS,
        "progress_percent": int((bounded_steps / _INGESTION_TOTAL_STEPS) * 100),
    }


def _streaming_headers() -> dict[str, str]:
    return {
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }


async def _run_ingestion_job(
    container,
    *,
    story_id: str,
    title: str,
    file_path: str,
) -> None:
    services = container.services
    started_at = perf_counter()
    initial_state = {
        "story_id": story_id,
        "title": title,
        "file_path": file_path,
        "raw_text": "",
        "graph_chunks": [],
        "vector_chunks": [],
        "graph_docs": [],
        "alias_map": {},
        "graph_built": False,
        "vectors_stored": False,
        "progress": [],
    }

    try:
        logger.info("ingestion job start | story_id=%s | title=%s | file_path=%s", story_id, title, file_path)
        await services.story_service.update_story_status(story_id, "running")
        await services.job_service.set_job_status(story_id, "running")
        completed_nodes: list[str] = []

        async for update in container.ingestion_graph.astream(
            initial_state,
            stream_mode="updates",
        ):
            node_name = next(iter(update))
            node_output = update[node_name]
            progress = (node_output.get("progress") or [""])[-1]
            if node_name not in completed_nodes:
                completed_nodes.append(node_name)
            await services.job_service.append_progress(
                story_id,
                node=node_name,
                progress=progress,
                status="running",
                **_build_progress_metadata(node_name, len(completed_nodes)),
            )
            logger.info(
                "ingestion job progress | story_id=%s | node=%s | step=%d/%d | message=%s",
                story_id,
                node_name,
                len(completed_nodes),
                _INGESTION_TOTAL_STEPS,
                progress,
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
            **_build_progress_metadata("complete", _INGESTION_TOTAL_STEPS),
        )
        logger.info(
            "ingestion job complete | story_id=%s | entity_count=%d | relationship_count=%d | vector_chunks=%d | duration_ms=%d",
            story_id,
            entity_count,
            relationship_count,
            chunk_count,
            int((perf_counter() - started_at) * 1000),
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
            stage=_INGESTION_STAGE_LABELS["error"],
            step=0,
            total_steps=_INGESTION_TOTAL_STEPS,
            progress_percent=0,
        )
    finally:
        await services.job_service.release_ingestion_lock(story_id)
        services.file_service.cleanup(file_path)
        logger.info("ingestion job finalized | story_id=%s", story_id)


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
        await container.services.job_service.append_progress(
            story_id,
            node="queued",
            progress="Waiting for an ingestion worker to start",
            status="queued",
            **_build_progress_metadata("queued", 0),
        )
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


@router.delete("/{story_id}")
async def delete_story(story_id: str, container=Depends(get_container)) -> dict[str, str]:
    services = container.services
    # Order: Vector -> Graph -> Chats -> Metadata -> Job status
    await services.vector_service.delete_story_vectors(story_id)
    await services.graph_service.delete_story_graph(story_id)
    await services.chat_service.delete_story_chats(story_id)
    await services.story_service.delete_story(story_id)
    await services.job_service.set_job_status(story_id, "deleted")
    return {"status": "success", "message": f"Story {story_id} deleted."}


@router.get("/{story_id}/graph", response_model=GraphResponse)
async def get_story_graph(story_id: str, container=Depends(get_container)) -> GraphResponse:
    await container.services.story_service.get_story_detail(story_id)
    return await container.services.graph_service.fetch_story_graph(story_id)


@router.get("/{story_id}/chunks", response_model=StoryChunksResponse)
async def get_story_chunks(
    story_id: str,
    container=Depends(get_container),
) -> StoryChunksResponse:
    await container.services.story_service.get_story_detail(story_id)
    chunks = await container.services.vector_service.list_story_chunks(story_id)
    return StoryChunksResponse(story_id=story_id, chunks=chunks)


@router.get("/{story_id}/chats", response_model=list[ChatSummary])
async def list_story_chats(
    story_id: str,
    container=Depends(get_container),
) -> list[ChatSummary]:
    await container.services.story_service.get_story_detail(story_id)
    return await container.services.chat_service.list_story_chats(story_id)


@router.get("/{story_id}/chats/{chat_id}", response_model=ChatSummary)
async def get_story_chat(
    story_id: str,
    chat_id: str,
    container=Depends(get_container),
) -> ChatSummary:
    await container.services.story_service.get_story_detail(story_id)
    return await container.services.chat_service.get_chat(story_id, chat_id)


@router.get("/{story_id}/chats/{chat_id}/messages", response_model=ChatTranscriptResponse)
async def get_story_chat_messages(
    story_id: str,
    chat_id: str,
    container=Depends(get_container),
) -> ChatTranscriptResponse:
    await container.services.story_service.get_story_detail(story_id)
    await container.services.chat_service.get_chat(story_id, chat_id)
    snapshot = await container.query_graph.aget_state({"configurable": {"thread_id": chat_id}})
    values = getattr(snapshot, "values", {}) or {}
    transcript = values.get("transcript") or []
    return ChatTranscriptResponse(
        story_id=story_id,
        chat_id=chat_id,
        messages=[ChatMessage.model_validate(item) for item in transcript],
    )


@router.post("/{story_id}/chats/messages", response_model=ChatMessageResponse)
async def send_story_chat_message(
    story_id: str,
    request: ChatMessageRequest,
    container=Depends(get_container),
) -> ChatMessageResponse:
    story = await container.services.story_service.get_story_detail(story_id)
    if story.status != "complete":
        raise StoryNotReadyError(
            f"Story '{story.display_name}' is not ready for querying yet."
        )

    created_new_chat = request.chat_id is None
    chat_id = request.chat_id or str(uuid4())

    if not created_new_chat:
        await container.services.chat_service.get_chat(story_id, chat_id)

    user_message_id = str(uuid4())
    result = await container.query_graph.ainvoke(
        {
            "story_id": story_id,
            "question": request.message,
            "messages": [HumanMessage(content=request.message, id=user_message_id)],
            "transcript": [_build_user_transcript(request.message, user_message_id)],
            "query_type": "",
            "routing_reason": None,
            "cypher_query": None,
            "graph_results": None,
            "vector_results": None,
            "evidence": None,
            "answer": "",
            "citations": [],
        },
        config={"configurable": {"thread_id": chat_id}},
    )

    turn_count = _count_turns(result.get("transcript"))
    if created_new_chat:
        await container.services.chat_service.create_chat(story_id, chat_id, request.message)

    await container.services.chat_service.update_chat_after_turn(
        story_id,
        chat_id,
        user_message=request.message,
        answer=result["answer"],
        turn_count=turn_count,
    )

    return ChatMessageResponse(
        chat_id=chat_id,
        story_id=story_id,
        created_new_chat=created_new_chat,
        answer=result["answer"],
        query_type=result["query_type"],
        routing_reason=result.get("routing_reason"),
        citations=result["citations"],
        evidence=result.get("evidence"),
    )


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
    logger.info(
        "ingestion stream connected | story_id=%s | status=%s",
        story_id,
        job_status.get("status", "unknown"),
    )

    async def event_generator():
        index = 0
        while not await request.is_disconnected():
            events, index = await container.services.job_service.read_progress_since(story_id, index)
            for event in events:
                yield _sse_message("progress", event.model_dump())

            job = await container.services.job_service.get_job_status(story_id)
            status = job.get("status")
            if status == "complete":
                yield _sse_message("complete", job)
                break
            if status == "error":
                yield _sse_message("job_error", job)
                break

            await asyncio.sleep(container.settings.sse_poll_interval_seconds)
        logger.info("ingestion stream disconnected | story_id=%s", story_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers=_streaming_headers(),
    )
