"""Factories for OpenAI/LangChain-powered components."""

from __future__ import annotations

from dataclasses import dataclass

from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.core.config import Settings
from app.schemas.query import AnswerOutput, CypherOutput, RouterOutput
from app.schemas.state import DeduplicationOutput


@dataclass(slots=True)
class LLMProviders:
    chat_llm: ChatOpenAI
    embeddings: OpenAIEmbeddings
    deduplication_llm: object
    router_llm: object
    cypher_llm: object
    answer_llm: object
    graph_transformer: LLMGraphTransformer
    gleaning_transformer: LLMGraphTransformer


def _build_chat_llm(settings: Settings) -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.openai_chat_model,
        temperature=0,
        api_key=settings.openai_api_key,
    )


def _build_embeddings(settings: Settings) -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=settings.openai_embedding_model,
        api_key=settings.openai_api_key,
    )


def _build_transformer(
    settings: Settings,
    llm: ChatOpenAI,
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


def build_llm_providers(settings: Settings) -> LLMProviders:
    chat_llm = _build_chat_llm(settings)
    embeddings = _build_embeddings(settings)

    deduplication_llm = chat_llm.with_structured_output(DeduplicationOutput)
    router_llm = chat_llm.with_structured_output(RouterOutput)
    cypher_llm = chat_llm.with_structured_output(CypherOutput)
    answer_llm = chat_llm.with_structured_output(AnswerOutput)

    gleaning_prompt = (
        "Review the story excerpt again carefully. "
        "Identify any characters, places, events, or relationships that were missed in "
        "the first pass. Only return NEW entities and relationships not already found."
    )

    return LLMProviders(
        chat_llm=chat_llm,
        embeddings=embeddings,
        deduplication_llm=deduplication_llm,
        router_llm=router_llm,
        cypher_llm=cypher_llm,
        answer_llm=answer_llm,
        graph_transformer=_build_transformer(settings, chat_llm),
        gleaning_transformer=_build_transformer(
            settings,
            chat_llm,
            additional_instructions=gleaning_prompt,
        ),
    )

