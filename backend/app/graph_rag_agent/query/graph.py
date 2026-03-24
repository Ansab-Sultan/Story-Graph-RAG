"""LangGraph workflow for story querying."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langgraph.graph import END, StateGraph

from app.graph_rag_agent.query.prompts import (
    build_answer_prompt,
    build_cypher_prompt,
    build_router_prompt,
)
from app.schemas.query import AnswerOutput, CypherOutput, RouterOutput
from app.schemas.state import QueryState
from app.services.container import ServiceContainer


@dataclass(slots=True)
class QueryWorkflow:
    services: ServiceContainer

    async def router(self, state: QueryState) -> dict[str, Any]:
        result: RouterOutput = await self.services.llm_providers.router_llm.ainvoke(
            build_router_prompt(state["question"])
        )
        return {"query_type": result.query_type}

    async def cypher_generator(self, state: QueryState) -> dict[str, Any]:
        result: CypherOutput = await self.services.llm_providers.cypher_llm.ainvoke(
            build_cypher_prompt(
                story_id=state["story_id"],
                question=state["question"],
                allowed_relationships=self.services.settings.allowed_relationship_types,
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
        vector_results = await self.services.vector_service.similarity_search(
            state["story_id"],
            state["question"],
            limit=self.services.settings.query_top_k,
        )
        return {"vector_results": vector_results}

    async def answer_synthesizer(self, state: QueryState) -> dict[str, Any]:
        if not state.get("graph_results") and not state.get("vector_results"):
            return {
                "answer": "I could not find enough evidence in the selected story to answer that question.",
                "citations": [],
            }

        result: AnswerOutput = await self.services.llm_providers.answer_llm.ainvoke(
            build_answer_prompt(
                question=state["question"],
                query_type=state["query_type"],
                graph_results=state.get("graph_results"),
                vector_results=state.get("vector_results"),
            )
        )
        return {
            "answer": result.answer,
            "citations": [citation.model_dump() for citation in result.citations],
        }


def _route_query(state: QueryState) -> str:
    if state["query_type"] == "vector":
        return "vector_only"
    if state["query_type"] == "graph":
        return "graph_only"
    return "hybrid"


def compile_query_graph(services: ServiceContainer):
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
    return builder.compile()
