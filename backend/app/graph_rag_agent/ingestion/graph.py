"""LangGraph workflow for story ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_community.graphs.graph_document import GraphDocument, Node, Relationship
from langchain_core.documents import Document
from langgraph.graph import END, StateGraph

from app.core.llm_config import build_contextual_gleaning_transformer
from app.graph_rag_agent.ingestion.prompts import build_deduplication_prompt
from app.graph_rag_agent.ingestion.state import IngestionState
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
        merged: list[GraphDocument] = []
        for index, chunk in enumerate(state["chunks"]):
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

        return {
            "graph_docs": deduplicated_docs,
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
