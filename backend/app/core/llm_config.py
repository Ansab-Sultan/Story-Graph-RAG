"""Factories for Mistral AI and local embedding components."""

from __future__ import annotations

import os
from dataclasses import dataclass
from textwrap import dedent

from langchain_community.embeddings import HuggingFaceBgeEmbeddings
from langchain_core.embeddings import Embeddings
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_mistralai import ChatMistralAI

# from langchain_google_genai import ChatGoogleGenerativeAI  # Gemini — commented out

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
    chat_llm: ChatMistralAI
    embeddings: Embeddings
    deduplication_llm: object
    router_llm: object
    cypher_llm: object
    answer_llm: object
    graph_transformer: LLMGraphTransformer


def _build_chat_llm(settings: Settings) -> ChatMistralAI:
    if settings.mistral_api_key:
        os.environ["MISTRAL_API_KEY"] = settings.mistral_api_key

    return ChatMistralAI(
        model=settings.mistral_model,
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
    llm: ChatMistralAI,
    additional_instructions: str | None = None,
) -> LLMGraphTransformer:
    from app.core.constants import GRAPH_EXTRACTION_INSTRUCTIONS

    instructions = GRAPH_EXTRACTION_INSTRUCTIONS
    if additional_instructions:
        instructions += "\n\n" + additional_instructions

    return LLMGraphTransformer(
        llm=llm,
        node_properties=["description"],
        relationship_properties=["description"],
        additional_instructions=instructions,
    )


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
    llm: ChatMistralAI,
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
