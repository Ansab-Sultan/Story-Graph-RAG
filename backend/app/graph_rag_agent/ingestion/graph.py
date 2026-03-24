"""LangGraph workflow for story ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langgraph.graph import END, StateGraph

from app.graph_rag_agent.ingestion.prompts import build_deduplication_prompt
from app.schemas.state import DeduplicationOutput, IngestionState
from app.services.container import ServiceContainer


@dataclass(slots=True)
class IngestionWorkflow:
    services: ServiceContainer

    async def loader(self, state: IngestionState) -> dict[str, Any]:
        file_path = Path(state["file_path"])
        raw_text = self.services.file_service.load_raw_text(file_path)
        chunks = self.services.file_service.build_chunks(state["story_id"], raw_text)
        return {
            "raw_text": raw_text,
            "chunks": chunks,
            "progress": state["progress"] + [f"✓ Split into {len(chunks)} chunks"],
        }

    async def graph_extractor(self, state: IngestionState) -> dict[str, Any]:
        graph_docs = await self.services.llm_providers.graph_transformer.aconvert_to_graph_documents(
            state["chunks"]
        )
        return {
            "graph_docs": graph_docs,
            "progress": state["progress"] + [f"✓ Extracted graph from {len(state['chunks'])} chunks"],
        }

    async def gleaning(self, state: IngestionState) -> dict[str, Any]:
        gleaned_docs = await self.services.llm_providers.gleaning_transformer.aconvert_to_graph_documents(
            state["chunks"]
        )
        merged = list(state["graph_docs"])
        for original, gleaned in zip(merged, gleaned_docs, strict=False):
            existing_ids = {node.id for node in original.nodes}
            for node in gleaned.nodes:
                if node.id not in existing_ids:
                    original.nodes.append(node)
            original.relationships.extend(gleaned.relationships)
        return {
            "graph_docs": merged,
            "progress": state["progress"] + ["✓ Gleaning pass complete"],
        }

    async def deduplication(self, state: IngestionState) -> dict[str, Any]:
        all_names = sorted(
            {
                node.id
                for doc in state["graph_docs"]
                for node in doc.nodes
            }
        )
        result: DeduplicationOutput = await self.services.llm_providers.deduplication_llm.ainvoke(
            build_deduplication_prompt(all_names)
        )
        alias_map: dict[str, str] = {}
        for group in result.groups:
            for alias in group.aliases:
                alias_map[alias] = group.canonical_name

        for doc in state["graph_docs"]:
            for node in doc.nodes:
                node.id = alias_map.get(node.id, node.id)
            for rel in doc.relationships:
                rel.source.id = alias_map.get(rel.source.id, rel.source.id)
                rel.target.id = alias_map.get(rel.target.id, rel.target.id)

        return {
            "graph_docs": state["graph_docs"],
            "alias_map": alias_map,
            "progress": state["progress"] + [f"✓ Deduplicated {len(alias_map)} aliases"],
        }

    async def graph_builder(self, state: IngestionState) -> dict[str, Any]:
        await self.services.graph_service.upsert_graph_documents(state["story_id"], state["graph_docs"])
        return {
            "graph_built": True,
            "progress": state["progress"] + ["✓ Knowledge graph written to local Neo4j"],
        }

    async def vector_embedder(self, state: IngestionState) -> dict[str, Any]:
        await self.services.vector_service.upsert_chunks(state["story_id"], state["chunks"])
        return {
            "vectors_stored": True,
            "progress": state["progress"] + [f"✓ {len(state['chunks'])} chunks embedded into local Qdrant"],
        }


def compile_ingestion_graph(services: ServiceContainer):
    workflow = IngestionWorkflow(services=services)
    builder = StateGraph(IngestionState)
    builder.add_node("loader", workflow.loader)
    builder.add_node("graph_extractor", workflow.graph_extractor)
    builder.add_node("gleaning", workflow.gleaning)
    builder.add_node("deduplication", workflow.deduplication)
    builder.add_node("graph_builder", workflow.graph_builder)
    builder.add_node("vector_embedder", workflow.vector_embedder)

    builder.set_entry_point("loader")
    builder.add_edge("loader", "graph_extractor")
    builder.add_edge("graph_extractor", "gleaning")
    builder.add_edge("gleaning", "deduplication")
    builder.add_edge("deduplication", "graph_builder")
    builder.add_edge("deduplication", "vector_embedder")
    builder.add_edge("graph_builder", END)
    builder.add_edge("vector_embedder", END)
    return builder.compile()

