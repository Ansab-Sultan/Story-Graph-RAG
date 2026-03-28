"""Neo4j-backed graph persistence and traversal helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re
from typing import Any

from neo4j import AsyncDriver
from neo4j.graph import Node as Neo4jNode
from neo4j.graph import Path as Neo4jPath
from neo4j.graph import Relationship as Neo4jRelationship

from app.core.config import Settings
from app.core.constants import GRAPH_ENTITY_LABEL
from app.core.exceptions import InfrastructureError
from app.schemas.graph import GraphEdge, GraphNode, GraphResponse
from app.schemas.story import GraphAnswerEvidence


@dataclass(slots=True)
class GraphService:
    driver: AsyncDriver
    settings: Settings

    async def ensure_indexes(self) -> None:
        async with self.driver.session() as session:
            await session.run(
                f"CREATE INDEX entity_name_story_id IF NOT EXISTS FOR (n:{GRAPH_ENTITY_LABEL}) "
                "ON (n.story_id, n.name)"
            )
            await session.run(
                f"CREATE INDEX entity_type IF NOT EXISTS FOR (n:{GRAPH_ENTITY_LABEL}) ON (n.type)"
            )

    async def upsert_graph_documents(self, story_id: str, graph_docs: list[Any]) -> None:
        async with self.driver.session() as session:
            for doc in graph_docs:
                for node in doc.nodes:
                    await session.run(
                        f"""
                        MERGE (e:{GRAPH_ENTITY_LABEL} {{name: $name, story_id: $story_id}})
                        SET e.type = $type, e.description = $description
                        """,
                        name=node.id,
                        story_id=story_id,
                        type=node.type,
                        description=node.properties.get("description", ""),
                    )

                for relationship in doc.relationships:
                    rel_type = self._sanitize_relationship_type(relationship.type)
                    await session.run(
                        f"""
                        MATCH (source:{GRAPH_ENTITY_LABEL} {{name: $source, story_id: $story_id}})
                        MATCH (target:{GRAPH_ENTITY_LABEL} {{name: $target, story_id: $story_id}})
                        MERGE (source)-[rel:{rel_type}]->(target)
                        SET rel.description = $description
                        """,
                        source=relationship.source.id,
                        target=relationship.target.id,
                        story_id=story_id,
                        description=relationship.properties.get("description", ""),
                    )

    async def get_story_counts(self, story_id: str) -> tuple[int, int]:
        async with self.driver.session() as session:
            entity_result = await session.run(
                f"MATCH (n:{GRAPH_ENTITY_LABEL} {{story_id: $story_id}}) RETURN count(n) AS count",
                story_id=story_id,
            )
            relationship_result = await session.run(
                f"""
                MATCH (:{GRAPH_ENTITY_LABEL} {{story_id: $story_id}})-[r]->(:{GRAPH_ENTITY_LABEL} {{story_id: $story_id}})
                RETURN count(r) AS count
                """,
                story_id=story_id,
            )
            entity_count_record = await entity_result.single()
            relationship_count_record = await relationship_result.single()
            return (
                int(entity_count_record["count"]) if entity_count_record else 0,
                int(relationship_count_record["count"]) if relationship_count_record else 0,
            )

    async def fetch_story_graph(self, story_id: str) -> GraphResponse:
        async with self.driver.session() as session:
            node_result = await session.run(
                f"""
                MATCH (n:{GRAPH_ENTITY_LABEL} {{story_id: $story_id}})
                RETURN n.name AS id, n.name AS label, n.type AS type, coalesce(n.description, '') AS description
                ORDER BY n.name
                """,
                story_id=story_id,
            )
            relationship_result = await session.run(
                f"""
                MATCH (source:{GRAPH_ENTITY_LABEL} {{story_id: $story_id}})-[r]->(target:{GRAPH_ENTITY_LABEL} {{story_id: $story_id}})
                RETURN source.name AS source, target.name AS target, type(r) AS relationship_type, coalesce(r.description, '') AS description
                """,
                story_id=story_id,
            )
            nodes = [
                GraphNode(
                    id=record["id"],
                    label=record["label"],
                    type=record["type"],
                    description=record["description"],
                )
                async for record in node_result
            ]
            edges = [
                GraphEdge(
                    source=record["source"],
                    target=record["target"],
                    relationship_type=record["relationship_type"],
                    description=record["description"],
                )
                async for record in relationship_result
            ]
        return GraphResponse(story_id=story_id, nodes=nodes, edges=edges)

    async def delete_story_graph(self, story_id: str) -> None:
        async with self.driver.session() as session:
            await session.run(
                f"MATCH (n:{GRAPH_ENTITY_LABEL} {{story_id: $story_id}}) DETACH DELETE n",
                story_id=story_id,
            )

    async def execute_cypher(self, story_id: str, cypher: str) -> list[dict[str, Any]]:
        if "$story_id" not in cypher and story_id not in cypher:
            raise InfrastructureError("Generated Cypher is missing story_id scoping.")

        async with self.driver.session() as session:
            result = await session.run(cypher, story_id=story_id)
            return [record.data() async for record in result]

    def normalize_graph_results(self, graph_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [self._serialize_mapping(row) for row in graph_results]

    def build_answer_evidence(
        self,
        graph_results: list[dict[str, Any]] | None,
    ) -> GraphAnswerEvidence | None:
        if not graph_results:
            return None

        nodes: dict[str, GraphNode] = {}
        relationships: dict[tuple[str, str, str], GraphEdge] = {}

        def visit(value: Any) -> None:
            if isinstance(value, Mapping):
                kind = value.get("__kind__")
                if kind == "node":
                    node = GraphNode(
                        id=str(value["id"]),
                        label=str(value.get("label", value["id"])),
                        type=str(value.get("type") or ""),
                        description=_optional_str(value.get("description")),
                    )
                    nodes[node.id] = node
                    return
                if kind == "relationship":
                    relationship = GraphEdge(
                        source=str(value["source"]),
                        target=str(value["target"]),
                        relationship_type=str(value["relationship_type"]),
                        description=_optional_str(value.get("description")),
                    )
                    relationships[
                        (
                            relationship.source,
                            relationship.target,
                            relationship.relationship_type,
                        )
                    ] = relationship
                    return
                if kind == "path":
                    for node_value in value.get("nodes", []):
                        visit(node_value)
                    for relationship_value in value.get("relationships", []):
                        visit(relationship_value)
                    return

                for nested_value in value.values():
                    visit(nested_value)
                return

            if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
                for item in value:
                    visit(item)

        for row in graph_results:
            visit(row)

        return GraphAnswerEvidence(
            nodes=list(nodes.values()),
            relationships=list(relationships.values()),
            raw_results=graph_results,
        )

    @staticmethod
    def _sanitize_relationship_type(relationship_type: str) -> str:
        sanitized = relationship_type.upper().strip()
        sanitized = re.sub(r"[^A-Z0-9]", "_", sanitized)
        sanitized = re.sub(r"_+", "_", sanitized).strip("_")
        return sanitized or "RELATED_TO"

    async def get_story_schema(self, story_id: str) -> dict[str, list[str]]:
        async with self.driver.session() as session:
            node_result = await session.run(
                f"MATCH (n:{GRAPH_ENTITY_LABEL} {{story_id: $story_id}}) "
                "RETURN DISTINCT n.type AS type",
                story_id=story_id,
            )
            rel_result = await session.run(
                f"MATCH (:{GRAPH_ENTITY_LABEL} {{story_id: $story_id}})"
                f"-[r]->(:{GRAPH_ENTITY_LABEL} {{story_id: $story_id}}) "
                "RETURN DISTINCT type(r) AS type",
                story_id=story_id,
            )
            node_types = [r["type"] async for r in node_result if r["type"]]
            rel_types = [r["type"] async for r in rel_result if r["type"]]
        return {"node_types": sorted(node_types), "relationship_types": sorted(rel_types)}

    def _serialize_mapping(self, value: Mapping[str, Any]) -> dict[str, Any]:
        return {key: self._serialize_value(item) for key, item in value.items()}

    def _serialize_value(self, value: Any) -> Any:
        if isinstance(value, Neo4jNode):
            return self._serialize_node(value)
        if isinstance(value, Neo4jRelationship):
            return self._serialize_relationship(value)
        if isinstance(value, Neo4jPath):
            return {
                "__kind__": "path",
                "nodes": [self._serialize_node(node) for node in value.nodes],
                "relationships": [
                    self._serialize_relationship(relationship)
                    for relationship in value.relationships
                ],
            }
        if isinstance(value, Mapping):
            return self._serialize_mapping(value)
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
            return [self._serialize_value(item) for item in value]
        return value

    def _serialize_node(self, node: Neo4jNode) -> dict[str, Any]:
        properties = {key: self._serialize_value(item) for key, item in dict(node.items()).items()}
        node_id = str(properties.get("name") or node.element_id)
        return {
            "__kind__": "node",
            "id": node_id,
            "label": node_id,
            "type": _optional_str(properties.get("type")) or "",
            "description": _optional_str(properties.get("description")),
            "properties": properties,
        }

    def _serialize_relationship(self, relationship: Neo4jRelationship) -> dict[str, Any]:
        properties = {
            key: self._serialize_value(item) for key, item in dict(relationship.items()).items()
        }
        start_node = relationship.start_node
        end_node = relationship.end_node
        source = str(start_node.get("name") or start_node.element_id) if start_node else ""
        target = str(end_node.get("name") or end_node.element_id) if end_node else ""
        return {
            "__kind__": "relationship",
            "source": source,
            "target": target,
            "relationship_type": relationship.type,
            "description": _optional_str(properties.get("description")),
            "properties": properties,
        }


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
