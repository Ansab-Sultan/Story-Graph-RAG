"""Factories for Gemini and local embedding components."""

from __future__ import annotations

import os
from dataclasses import dataclass
from textwrap import dedent

from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_core.embeddings import Embeddings
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from app.core.config import Settings
from app.schemas.query import AnswerOutput, CypherOutput, RouterOutput


class DuplicateGroup(BaseModel):
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)


class DeduplicationOutput(BaseModel):
    groups: list[DuplicateGroup] = Field(default_factory=list)


@dataclass(slots=True)
class LLMProviders:
    chat_llm: ChatGoogleGenerativeAI
    embeddings: Embeddings
    deduplication_llm: object
    router_llm: object
    cypher_llm: object
    answer_llm: object
    graph_transformer: LLMGraphTransformer


def _build_chat_llm(settings: Settings) -> ChatGoogleGenerativeAI:
    if settings.google_api_key:
        os.environ["GOOGLE_API_KEY"] = settings.google_api_key
    return ChatGoogleGenerativeAI(
        model=settings.google_chat_model,
        temperature=0,
    )


def _build_embeddings(settings: Settings) -> Embeddings:
    return HuggingFaceBgeEmbeddings(
        model_name=settings.embedding_model,
        model_kwargs={"device": settings.embedding_device},
        encode_kwargs={"normalize_embeddings": settings.embedding_normalize},
    )


def _build_transformer(
    settings: Settings,
    llm: ChatGoogleGenerativeAI,
    additional_instructions: str | None = None,
) -> LLMGraphTransformer:
    kwargs: dict[str, object] = {
        "llm": llm,
        "allowed_nodes": list(settings.allowed_node_types),
        "allowed_relationships": list(settings.allowed_relationship_types),
        "node_properties": ["description"],
        "relationship_properties": ["description"],
    }
    if additional_instructions:
        kwargs["additional_instructions"] = additional_instructions
    return LLMGraphTransformer(**kwargs)


def build_gleaning_instructions(existing_graph_context: str) -> str:
    return dedent(
        f"""
        Review the story excerpt again carefully.
        The following entities and relationships were already extracted from this same excerpt:
        {existing_graph_context}

        Only return genuinely NEW entities and relationships that are explicitly stated in the text
        and do not already appear in the existing extraction above.
        Do not repeat existing entities or existing relationships.
        If there are no new entities or relationships left to extract, return empty node and relationship lists.
        """
    ).strip()


def build_contextual_gleaning_transformer(
    settings: Settings,
    llm: ChatGoogleGenerativeAI,
    existing_graph_context: str,
) -> LLMGraphTransformer:
    return _build_transformer(
        settings,
        llm,
        additional_instructions=build_gleaning_instructions(existing_graph_context),
    )


def build_llm_providers(settings: Settings) -> LLMProviders:
    chat_llm = _build_chat_llm(settings)
    embeddings = _build_embeddings(settings)

    deduplication_llm = chat_llm.with_structured_output(DeduplicationOutput)
    router_llm = chat_llm.with_structured_output(RouterOutput)
    cypher_llm = chat_llm.with_structured_output(CypherOutput)
    answer_llm = chat_llm.with_structured_output(AnswerOutput)

    return LLMProviders(
        chat_llm=chat_llm,
        embeddings=embeddings,
        deduplication_llm=deduplication_llm,
        router_llm=router_llm,
        cypher_llm=cypher_llm,
        answer_llm=answer_llm,
        graph_transformer=_build_transformer(settings, chat_llm),
    )
