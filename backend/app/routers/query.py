"""Story query routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.dependencies import get_container
from app.core.exceptions import StoryNotReadyError
from app.schemas.query import QueryRequest, QueryResponse

router = APIRouter(prefix="/api/stories", tags=["query"])


@router.post("/{story_id}/query", response_model=QueryResponse)
async def query_story(
    story_id: str,
    request: QueryRequest,
    container=Depends(get_container),
) -> QueryResponse:
    story = await container.services.story_service.get_story_detail(story_id)
    if story.status != "complete":
        raise StoryNotReadyError(
            f"Story '{story.display_name}' is not ready for querying yet."
        )

    result = await container.query_graph.ainvoke(
        {
            "story_id": story_id,
            "question": request.question,
            "query_type": "",
            "cypher_query": None,
            "graph_results": None,
            "vector_results": None,
            "answer": "",
            "citations": [],
        }
    )
    await container.services.story_service.append_qa(
        story_id,
        question=request.question,
        answer=result["answer"],
        query_type=result["query_type"],
        citations=result["citations"],
    )
    return QueryResponse(
        answer=result["answer"],
        query_type=result["query_type"],
        citations=result["citations"],
    )
