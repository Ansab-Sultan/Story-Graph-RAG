"""Neo4j-backed graph persistence and traversal helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from neo4j import AsyncDriver

from app.core.config import Settings
from app.core.constants import GRAPH_ENTITY_LABEL
from app.core.exceptions import InfrastructureError
from app.schemas.graph import GraphEdge, GraphNode, GraphResponse


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
                RETURN n.name AS id, n.name AS label, n.type AS type, n.description AS description
                ORDER BY n.name
                """,
                story_id=story_id,
            )
            relationship_result = await session.run(
                f"""
                MATCH (source:{GRAPH_ENTITY_LABEL} {{story_id: $story_id}})-[r]->(target:{GRAPH_ENTITY_LABEL} {{story_id: $story_id}})
                RETURN source.name AS source, target.name AS target, type(r) AS relationship_type, r.description AS description
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

    async def execute_cypher(self, story_id: str, cypher: str) -> list[dict[str, Any]]:
        if "$story_id" not in cypher and story_id not in cypher:
            raise InfrastructureError("Generated Cypher is missing story_id scoping.")

        async with self.driver.session() as session:
            result = await session.run(cypher, story_id=story_id)
            return [record.data() async for record in result]

    def normalize_graph_results(self, graph_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for row in graph_results:
            for key, value in row.items():
                if hasattr(value, "items"):
                    normalized.append(dict(value.items()))
                else:
                    normalized.append({"key": key, "value": value})
        return normalized

    def _sanitize_relationship_type(self, relationship_type: str) -> str:
        if relationship_type not in self.settings.allowed_relationship_types:
            raise InfrastructureError(
                f"Unsupported relationship type '{relationship_type}' encountered during graph persistence."
            )
        return relationship_type

