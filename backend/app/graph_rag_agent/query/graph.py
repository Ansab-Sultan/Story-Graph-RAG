"""LangGraph workflow for story querying."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from langchain_core.messages import AIMessage
from langgraph.graph import END, StateGraph

from app.graph_rag_agent.query.prompts import (
    build_answer_prompt,
    build_cypher_prompt,
    build_router_prompt,
)
from app.graph_rag_agent.query.state import QueryState
from app.schemas.query import AnswerOutput, CypherOutput, RouterOutput
from app.schemas.story import ChunkResult, QueryEvidence
from app.services.container import ServiceContainer


def _build_query_evidence(
    services: ServiceContainer,
    state: QueryState,
) -> dict[str, Any] | None:
    graph_results = state.get("graph_results")
    vector_results = state.get("vector_results")

    graph_evidence = None
    if graph_results:
        graph_evidence = services.graph_service.build_answer_evidence(graph_results)

    chunk_items: list[ChunkResult] = []
    chunk_ids: list[str] = []
    if vector_results:
        for item in vector_results:
            chunk_id = item.get("chunk_id")
            if not chunk_id:
                continue
            chunk_items.append(
                ChunkResult(
                    chunk_id=str(chunk_id),
                    chunk_index=item.get("chunk_index"),
                    text=item.get("text"),
                    score=item.get("score"),
                )
            )
            chunk_ids.append(str(chunk_id))

    if graph_evidence is None and not chunk_items:
        return None

    return QueryEvidence(
        graph=graph_evidence,
        chunk_ids=list(dict.fromkeys(chunk_ids)),
        chunks=chunk_items,
    ).model_dump(mode="json")


def _build_contextual_search_query(
    question: str,
    transcript: list[dict[str, Any]] | None,
    history_limit: int,
) -> str:
    if not transcript:
        return question

    recent_messages = transcript[-history_limit:]
    conversation = [
        f"{item.get('role', 'user')}: {item.get('content', '')}"
        for item in recent_messages
        if item.get("content")
    ]
    return "\n".join(conversation) if conversation else question


def _build_assistant_transcript(
    state: QueryState,
    *,
    answer: str,
    citations: list[dict[str, Any]],
    evidence: dict[str, Any] | None,
    message_id: str,
) -> dict[str, Any]:
    return {
        "message_id": message_id,
        "role": "assistant",
        "content": answer,
        "created_at": datetime.now(UTC).isoformat(),
        "query_type": state["query_type"],
        "routing_reason": state.get("routing_reason"),
        "citations": citations,
        "evidence": evidence,
    }


@dataclass(slots=True)
class QueryWorkflow:
    services: ServiceContainer

    async def router(self, state: QueryState) -> dict[str, Any]:
        result: RouterOutput = await self.services.llm_providers.router_llm.ainvoke(
            build_router_prompt(
                messages=state["messages"],
                history_limit=self.services.settings.chat_prompt_history_messages,
            )
        )
        return {
            "query_type": result.query_type,
            "routing_reason": result.reasoning.strip(),
        }

    async def cypher_generator(self, state: QueryState) -> dict[str, Any]:
        schema = await self.services.graph_service.get_story_schema(state["story_id"])
        result: CypherOutput = await self.services.llm_providers.cypher_llm.ainvoke(
            build_cypher_prompt(
                story_id=state["story_id"],
                messages=state["messages"],
                node_types=schema["node_types"],
                relationship_types=schema["relationship_types"],
                history_limit=self.services.settings.chat_prompt_history_messages,
            )
        )
        return {"cypher_query": result.cypher}

    async def graph_retriever(self, state: QueryState) -> dict[str, Any]:
        graph_results = await self.services.graph_service.execute_cypher(
            state["story_id"],
            state["cypher_query"] or "",
        )
        return {
            "graph_results": self.services.graph_service.normalize_graph_results(graph_results),
        }

    async def vector_retriever(self, state: QueryState) -> dict[str, Any]:
        contextual_query = _build_contextual_search_query(
            state["question"],
            state.get("transcript"),
            self.services.settings.chat_prompt_history_messages,
        )
        vector_results = await self.services.vector_service.similarity_search(
            state["story_id"],
            contextual_query,
            limit=self.services.settings.query_top_k,
        )
        return {"vector_results": vector_results}

    async def answer_synthesizer(self, state: QueryState) -> dict[str, Any]:
        evidence = _build_query_evidence(self.services, state)

        if not state.get("graph_results") and not state.get("vector_results"):
            answer = (
                "I could not find enough evidence in the selected story to answer that question."
            )
            citations: list[dict[str, Any]] = []
        else:
            result: AnswerOutput = await self.services.llm_providers.answer_llm.ainvoke(
                build_answer_prompt(
                    query_type=state["query_type"],
                    graph_results=state.get("graph_results"),
                    vector_results=state.get("vector_results"),
                    messages=state["messages"],
                    history_limit=self.services.settings.chat_prompt_history_messages,
                )
            )
            answer = result.answer
            citations = [citation.model_dump() for citation in result.citations]

        assistant_message_id = str(uuid4())
        return {
            "answer": answer,
            "citations": citations,
            "evidence": evidence,
            "messages": [AIMessage(content=answer, id=assistant_message_id)],
            "transcript": [
                _build_assistant_transcript(
                    state,
                    answer=answer,
                    citations=citations,
                    evidence=evidence,
                    message_id=assistant_message_id,
                )
            ],
        }


def _route_query(state: QueryState) -> str:
    if state["query_type"] == "vector":
        return "vector_only"
    if state["query_type"] == "graph":
        return "graph_only"
    return "hybrid"


def compile_query_graph(services: ServiceContainer, checkpointer: Any | None = None):
    workflow = QueryWorkflow(services=services)
    builder = StateGraph(QueryState)
    builder.add_node("router", workflow.router)
    builder.add_node("cypher_generator", workflow.cypher_generator)
    builder.add_node("graph_retriever", workflow.graph_retriever)
    builder.add_node("vector_retriever", workflow.vector_retriever)
    builder.add_node("answer_synthesizer", workflow.answer_synthesizer)

    builder.set_entry_point("router")
    builder.add_conditional_edges(
        "router",
        _route_query,
        {
            "vector_only": "vector_retriever",
            "graph_only": "cypher_generator",
            "hybrid": "cypher_generator",
        },
    )
    builder.add_edge("cypher_generator", "graph_retriever")
    builder.add_conditional_edges(
        "graph_retriever",
        lambda current_state: (
            "vector_retriever"
            if current_state["query_type"] == "hybrid"
            else "answer_synthesizer"
        ),
        {
            "vector_retriever": "vector_retriever",
            "answer_synthesizer": "answer_synthesizer",
        },
    )
    builder.add_edge("vector_retriever", "answer_synthesizer")
    builder.add_edge("answer_synthesizer", END)
    return builder.compile(checkpointer=checkpointer)
