"""LangGraph workflow for story ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from langchain_community.graphs.graph_document import GraphDocument, Node, Relationship
from langchain_core.documents import Document
from langgraph.graph import END, StateGraph

from app.core.llm_config import build_contextual_gleaning_transformer
from app.core.logging import get_logger
from app.graph_rag_agent.ingestion.prompts import build_deduplication_prompt
from app.graph_rag_agent.ingestion.state import IngestionState
from app.services.container import ServiceContainer

logger = get_logger(__name__)
_STAGE_LABELS = {
    "graph_extractor": "Extracting Graph",
    "gleaning": "Gleaning Details",
    "deduplication": "Deduplicating Entities",
    "graph_builder": "Writing Neo4j Graph",
    "vector_embedder": "Embedding for Qdrant",
}
_STAGE_START_STEPS = {
    "graph_extractor": 2,
    "gleaning": 3,
    "deduplication": 4,
    "graph_builder": 5,
    "vector_embedder": 5,
}
_TOTAL_STEPS = 6


@dataclass(slots=True)
class IngestionWorkflow:
    services: ServiceContainer

    async def _emit_stage_event(
        self,
        *,
        story_id: str,
        node: str,
        progress: str,
        fraction: float,
    ) -> None:
        job_service = getattr(self.services, "job_service", None)
        if job_service is None:
            return

        step = _STAGE_START_STEPS[node]
        bounded_fraction = max(0.0, min(fraction, 0.99))
        progress_percent = int((((step - 1) + bounded_fraction) / _TOTAL_STEPS) * 100)
        await job_service.append_progress(
            story_id,
            node=node,
            progress=progress,
            status="running",
            stage=_STAGE_LABELS[node],
            step=step,
            total_steps=_TOTAL_STEPS,
            progress_percent=progress_percent,
        )

    async def loader(self, state: IngestionState) -> dict[str, Any]:
        started_at = perf_counter()
        file_path = Path(state["file_path"])
        raw_text = self.services.file_service.load_raw_text(file_path)
        graph_chunks = self.services.file_service.build_graph_chunks(state["story_id"], raw_text)
        vector_chunks = self.services.file_service.build_vector_chunks(state["story_id"], raw_text)
        logger.info(
            "ingestion stage=loader complete | story_id=%s | raw_chars=%d | graph_chunks=%d | vector_chunks=%d | graph_chunk_size=%d | graph_chunk_overlap=%d | vector_chunk_size=%d | vector_chunk_overlap=%d | duration_ms=%d",
            state["story_id"],
            len(raw_text),
            len(graph_chunks),
            len(vector_chunks),
            self.services.settings.graph_chunk_size,
            self.services.settings.graph_chunk_overlap,
            self.services.settings.vector_chunk_size,
            self.services.settings.vector_chunk_overlap,
            int((perf_counter() - started_at) * 1000),
        )
        return {
            "raw_text": raw_text,
            "graph_chunks": graph_chunks,
            "vector_chunks": vector_chunks,
            "progress": state["progress"]
            + [f"✓ Built {len(graph_chunks)} graph chunks and {len(vector_chunks)} vector chunks"],
        }

    async def graph_extractor(self, state: IngestionState) -> dict[str, Any]:
        started_at = perf_counter()
        await self._emit_stage_event(
            story_id=state["story_id"],
            node="graph_extractor",
            progress=f"Submitting {len(state['graph_chunks'])} large graph chunks to the LLM",
            fraction=0.12,
        )
        logger.info(
            "ingestion stage=graph_extractor start | story_id=%s | graph_chunks=%d",
            state["story_id"],
            len(state["graph_chunks"]),
        )
        graph_docs = await self.services.llm_providers.graph_transformer.aconvert_to_graph_documents(
            state["graph_chunks"]
        )
        logger.info(
            "ingestion stage=graph_extractor complete | story_id=%s | graph_docs=%d | duration_ms=%d",
            state["story_id"],
            len(graph_docs),
            int((perf_counter() - started_at) * 1000),
        )
        return {
            "graph_docs": graph_docs,
            "progress": state["progress"]
            + [f"✓ Extracted graph from {len(state['graph_chunks'])} graph chunks"],
        }

    async def gleaning(self, state: IngestionState) -> dict[str, Any]:
        started_at = perf_counter()
        await self._emit_stage_event(
            story_id=state["story_id"],
            node="gleaning",
            progress=f"Reviewing {len(state['graph_chunks'])} graph chunks for missed entities and relationships",
            fraction=0.08,
        )
        logger.info(
            "ingestion stage=gleaning start | story_id=%s | graph_chunks=%d",
            state["story_id"],
            len(state["graph_chunks"]),
        )
        merged: list[GraphDocument] = []
        for index, chunk in enumerate(state["graph_chunks"]):
            chunk_started_at = perf_counter()
            original = (
                state["graph_docs"][index]
                if index < len(state["graph_docs"])
                else GraphDocument(nodes=[], relationships=[], source=chunk)
            )
            existing_graph_context = _format_existing_graph_context(original)
            transformer = build_contextual_gleaning_transformer(
                self.services.settings,
                self.services.llm_providers.chat_llm,
                existing_graph_context,
            )
            gleaned = await transformer.aprocess_response(chunk)
            merged.append(_merge_graph_documents(original, gleaned))
            await self._emit_stage_event(
                story_id=state["story_id"],
                node="gleaning",
                progress=(
                    f"Gleaning chunk {index + 1}/{len(state['graph_chunks'])} for additional entities and relationships"
                ),
                fraction=0.2 + (0.7 * ((index + 1) / max(len(state["graph_chunks"]), 1))),
            )
            logger.info(
                "ingestion stage=gleaning chunk_complete | story_id=%s | chunk_index=%d | total_chunks=%d | duration_ms=%d",
                state["story_id"],
                index,
                len(state["graph_chunks"]),
                int((perf_counter() - chunk_started_at) * 1000),
            )
        logger.info(
            "ingestion stage=gleaning complete | story_id=%s | merged_docs=%d | duration_ms=%d",
            state["story_id"],
            len(merged),
            int((perf_counter() - started_at) * 1000),
        )
        return {
            "graph_docs": merged,
            "progress": state["progress"] + ["✓ Gleaning pass complete"],
        }

    async def deduplication(self, state: IngestionState) -> dict[str, Any]:
        started_at = perf_counter()
        await self._emit_stage_event(
            story_id=state["story_id"],
            node="deduplication",
            progress="Grouping aliases and choosing canonical entity names",
            fraction=0.1,
        )
        logger.info(
            "ingestion stage=deduplication start | story_id=%s | graph_docs=%d",
            state["story_id"],
            len(state["graph_docs"]),
        )
        all_names = sorted(
            {
                node.id
                for doc in state["graph_docs"]
                for node in doc.nodes
            }
        )
        result = await self.services.llm_providers.deduplication_llm.ainvoke(
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

        deduplicated_docs = [_deduplicate_graph_document(doc) for doc in state["graph_docs"]]
        logger.info(
            "ingestion stage=deduplication complete | story_id=%s | input_names=%d | aliases=%d | duration_ms=%d",
            state["story_id"],
            len(all_names),
            len(alias_map),
            int((perf_counter() - started_at) * 1000),
        )

        return {
            "graph_docs": deduplicated_docs,
            "alias_map": alias_map,
            "progress": state["progress"] + [f"✓ Deduplicated {len(alias_map)} aliases"],
        }

    async def graph_builder(self, state: IngestionState) -> dict[str, Any]:
        started_at = perf_counter()
        await self._emit_stage_event(
            story_id=state["story_id"],
            node="graph_builder",
            progress="Writing normalized entities and relationships to Neo4j",
            fraction=0.1,
        )
        logger.info(
            "ingestion stage=graph_builder start | story_id=%s | graph_docs=%d",
            state["story_id"],
            len(state["graph_docs"]),
        )
        await self.services.graph_service.upsert_graph_documents(state["story_id"], state["graph_docs"])
        logger.info(
            "ingestion stage=graph_builder complete | story_id=%s | duration_ms=%d",
            state["story_id"],
            int((perf_counter() - started_at) * 1000),
        )
        return {
            "graph_built": True,
            "progress": state["progress"] + ["✓ Knowledge graph written to local Neo4j"],
        }

    async def vector_embedder(self, state: IngestionState) -> dict[str, Any]:
        started_at = perf_counter()
        await self._emit_stage_event(
            story_id=state["story_id"],
            node="vector_embedder",
            progress=f"Embedding {len(state['vector_chunks'])} retrieval chunks and uploading them to Qdrant",
            fraction=0.1,
        )
        logger.info(
            "ingestion stage=vector_embedder start | story_id=%s | vector_chunks=%d",
            state["story_id"],
            len(state["vector_chunks"]),
        )
        await self.services.vector_service.upsert_chunks(state["story_id"], state["vector_chunks"])
        logger.info(
            "ingestion stage=vector_embedder complete | story_id=%s | vector_chunks=%d | duration_ms=%d",
            state["story_id"],
            len(state["vector_chunks"]),
            int((perf_counter() - started_at) * 1000),
        )
        return {
            "vectors_stored": True,
            "progress": state["progress"]
            + [f"✓ {len(state['vector_chunks'])} vector chunks embedded into local Qdrant"],
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


def _format_existing_graph_context(graph_doc: GraphDocument) -> str:
    node_lines = [
        _format_node_line(node)
        for node in _ordered_unique_nodes(graph_doc)
    ]
    relationship_lines = [
        _format_relationship_line(relationship)
        for relationship in _ordered_unique_relationships(graph_doc)
    ]
    nodes_section = node_lines or ["- none"]
    relationships_section = relationship_lines or ["- none"]
    return "\n".join(
        [
            "Existing nodes:",
            *nodes_section,
            "Existing relationships:",
            *relationships_section,
        ]
    )


def _merge_graph_documents(original: GraphDocument, gleaned: GraphDocument) -> GraphDocument:
    merged_nodes: dict[str, Node] = {}
    for node in _all_candidate_nodes(original, gleaned):
        key = _normalize_identifier(node.id)
        if key in merged_nodes:
            _merge_node_into(merged_nodes[key], node)
        else:
            merged_nodes[key] = node.model_copy(deep=True)

    merged_relationships: dict[tuple[str, str, str], Relationship] = {}
    for relationship in list(original.relationships) + list(gleaned.relationships):
        source_key = _normalize_identifier(relationship.source.id)
        target_key = _normalize_identifier(relationship.target.id)
        canonical_source = merged_nodes[source_key]
        canonical_target = merged_nodes[target_key]
        relationship_key = (source_key, target_key, _normalize_identifier(relationship.type))

        if relationship_key in merged_relationships:
            _merge_relationship_into(merged_relationships[relationship_key], relationship)
            continue

        relationship_copy = relationship.model_copy(deep=True)
        relationship_copy.source = canonical_source.model_copy(deep=True)
        relationship_copy.target = canonical_target.model_copy(deep=True)
        merged_relationships[relationship_key] = relationship_copy

    return GraphDocument(
        nodes=list(merged_nodes.values()),
        relationships=list(merged_relationships.values()),
        source=original.source if original.source else gleaned.source,
    )


def _deduplicate_graph_document(graph_doc: GraphDocument) -> GraphDocument:
    return _merge_graph_documents(
        graph_doc,
        GraphDocument(nodes=[], relationships=[], source=graph_doc.source or Document(page_content="")),
    )


def _all_candidate_nodes(*graph_docs: GraphDocument) -> list[Node]:
    nodes: list[Node] = []
    for graph_doc in graph_docs:
        nodes.extend(graph_doc.nodes)
        for relationship in graph_doc.relationships:
            nodes.append(relationship.source)
            nodes.append(relationship.target)
    return nodes


def _ordered_unique_nodes(graph_doc: GraphDocument) -> list[Node]:
    ordered: dict[str, Node] = {}
    for node in _all_candidate_nodes(graph_doc):
        key = _normalize_identifier(node.id)
        if key in ordered:
            _merge_node_into(ordered[key], node)
        else:
            ordered[key] = node.model_copy(deep=True)
    return list(ordered.values())


def _ordered_unique_relationships(graph_doc: GraphDocument) -> list[Relationship]:
    ordered: dict[tuple[str, str, str], Relationship] = {}
    for relationship in graph_doc.relationships:
        key = (
            _normalize_identifier(relationship.source.id),
            _normalize_identifier(relationship.target.id),
            _normalize_identifier(relationship.type),
        )
        if key in ordered:
            _merge_relationship_into(ordered[key], relationship)
        else:
            ordered[key] = relationship.model_copy(deep=True)
    return list(ordered.values())


def _merge_node_into(target: Node, incoming: Node) -> None:
    target_type = str(target.type or "").strip()
    incoming_type = str(incoming.type or "").strip()
    if _should_replace_type(target_type, incoming_type):
        target.type = incoming_type

    target_id = str(target.id).strip()
    incoming_id = str(incoming.id).strip()
    if len(incoming_id) > len(target_id):
        target.id = incoming.id

    target.properties = _merge_properties(target.properties, incoming.properties)


def _merge_relationship_into(target: Relationship, incoming: Relationship) -> None:
    _merge_node_into(target.source, incoming.source)
    _merge_node_into(target.target, incoming.target)
    target.properties = _merge_properties(target.properties, incoming.properties)


def _merge_properties(
    target_properties: dict[str, Any],
    incoming_properties: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(target_properties)
    for key, value in incoming_properties.items():
        if value in (None, ""):
            continue
        if key not in merged or merged[key] in (None, ""):
            merged[key] = value
            continue
        if key == "description":
            merged[key] = _prefer_description(str(merged[key]), str(value))
    return merged


def _prefer_description(existing: str, incoming: str) -> str:
    existing_clean = existing.strip()
    incoming_clean = incoming.strip()
    if not existing_clean:
        return incoming_clean
    if not incoming_clean:
        return existing_clean
    return incoming_clean if len(incoming_clean) > len(existing_clean) else existing_clean


def _should_replace_type(existing_type: str, incoming_type: str) -> bool:
    if not incoming_type:
        return False
    if not existing_type:
        return True
    if existing_type.lower() == "node" and incoming_type.lower() != "node":
        return True
    return False


def _format_node_line(node: Node) -> str:
    description = str(node.properties.get("description", "")).strip()
    suffix = f' description="{description}"' if description else ""
    return f"- {node.id} [{node.type}]{suffix}"


def _format_relationship_line(relationship: Relationship) -> str:
    description = str(relationship.properties.get("description", "")).strip()
    suffix = f' description="{description}"' if description else ""
    return (
        f"- {relationship.source.id} -[{relationship.type}]-> {relationship.target.id}{suffix}"
    )


def _normalize_identifier(value: Any) -> str:
    return str(value).strip().casefold()
