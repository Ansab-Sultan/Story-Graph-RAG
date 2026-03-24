"""Qdrant-backed vector storage and retrieval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langchain_openai import OpenAIEmbeddings
from qdrant_client import AsyncQdrantClient
from qdrant_client.http import models

from app.core.config import Settings


@dataclass(slots=True)
class VectorService:
    client: AsyncQdrantClient
    embeddings: OpenAIEmbeddings
    settings: Settings

    def story_collection_name(self, story_id: str) -> str:
        return f"story_{story_id}"

    async def ensure_collection(self, story_id: str) -> None:
        collection_name = self.story_collection_name(story_id)
        exists = await self.client.collection_exists(collection_name=collection_name)
        if not exists:
            await self.client.create_collection(
                collection_name=collection_name,
                vectors_config=models.VectorParams(size=1536, distance=models.Distance.COSINE),
            )

    async def upsert_chunks(self, story_id: str, chunks: list[Any]) -> None:
        await self.ensure_collection(story_id)
        texts = [chunk.page_content for chunk in chunks]
        embeddings = await self.embeddings.aembed_documents(texts)
        points = [
            models.PointStruct(
                id=chunk.metadata["chunk_id"],
                vector=embeddings[index],
                payload={
                    "story_id": story_id,
                    "chunk_id": chunk.metadata["chunk_id"],
                    "chunk_index": chunk.metadata["chunk_index"],
                    "text": chunk.page_content,
                },
            )
            for index, chunk in enumerate(chunks)
        ]
        await self.client.upsert(
            collection_name=self.story_collection_name(story_id),
            points=points,
        )

    async def similarity_search(
        self,
        story_id: str,
        question: str,
        *,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        query_embedding = await self.embeddings.aembed_query(question)
        hits = await self.client.query_points(
            collection_name=self.story_collection_name(story_id),
            query=query_embedding,
            limit=limit or self.settings.query_top_k,
            with_payload=True,
        )
        return [
            {
                "score": point.score,
                "chunk_id": point.payload.get("chunk_id"),
                "chunk_index": point.payload.get("chunk_index"),
                "text": point.payload.get("text"),
            }
            for point in hits.points
        ]

    async def count_points(self, story_id: str) -> int:
        response = await self.client.count(
            collection_name=self.story_collection_name(story_id),
            count_filter=None,
            exact=True,
        )
        return response.count

