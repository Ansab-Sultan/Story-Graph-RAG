# Technical Specification
## Story GraphRAG — Intelligent Story & Novel Analysis Engine

**Version:** 1.0  
**Author:** Muhammad Ansab Sultan  
**Date:** March 2026  
**Status:** Draft

---

## 1. System Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                        User Browser                           │
│           React Frontend (Vite + TailwindCSS)                 │
│    [Upload] [Graph Viz] [Chat Interface] [History Sidebar]    │
└────────────────────────┬─────────────────────────────────────┘
                         │ HTTP / SSE
┌────────────────────────▼─────────────────────────────────────┐
│                    FastAPI Backend                             │
│         (Async REST API + SSE Streaming Endpoints)            │
│  main.py bootstraps app, builds service container, and runs   │
│ create_index.py on startup for story/chat MongoDB indexes and │
│                        Neo4j indexes                          │
└──────┬──────────────────────┬────────────────────────────────┘
       │                      │
┌──────▼──────┐      ┌────────▼────────┐
│  Ingestion  │      │   Query Agent   │
│  Pipeline   │      │  (LangGraph)    │
│ (LangGraph) │      │                 │
└──────┬──────┘      └────────┬────────┘
       │                      │
       │                Gemini API
       │         (gemini-3.1-flash-lite-preview)
       │
  ┌────▼──────────────────────▼──────────────────────┐
  │                  Local Data Layer                 │
  │ Neo4j │ Qdrant │ MongoDB │ Redis │ BGE Embeddings │
  └───────────────────────────────────────────────────┘
```

---

## 2. Tech Stack

| Layer | Technology | Reason |
|---|---|---|
| Agent Framework | LangGraph | Stateful graph execution for both ingestion pipeline and query routing agent |
| Query Memory | LangGraph `MongoDBSaver` | Persists query-agent state by `thread_id`, where `thread_id == chat_id` |
| LLM | Gemini `gemini-3.1-flash-lite-preview` | Graph extraction, deduplication, routing, Cypher generation, and answer generation |
| Graph Extraction | LangChain `LLMGraphTransformer` | Extracts nodes + relationships together in one async batched call using function calling |
| Text Splitting | LangChain `RecursiveCharacterTextSplitter` | Pure text chunking with two profiles: large graph chunks (`GRAPH_CHUNK_SIZE=9000`, `GRAPH_CHUNK_OVERLAP=1000`) and smaller vector chunks (`VECTOR_CHUNK_SIZE=600`, `VECTOR_CHUNK_OVERLAP=100`) |
| Structured Output | LangChain `.with_structured_output()` | Type-safe responses for deduplication, routing, Cypher generation, and answer synthesis |
| Graph Database | Local Neo4j | Self-hosted graph storage and Cypher traversal on the developer machine |
| Vector Database | Local Qdrant | Self-hosted semantic similarity search for chunk retrieval, currently run from `backend/qdrant/docker-compose.yml` |
| History Store | Local MongoDB (Motor async driver) | Self-hosted persistence for stories, file-name based selection, chat metadata, and LangGraph checkpoint collections |
| Embeddings | `BAAI/bge-small-en-v1.5` via `HuggingFaceBgeEmbeddings` | Local chunk and query embeddings stored in Qdrant only |
| Backend | FastAPI (fully async) | Async endpoints, SSE streaming, BackgroundTasks for ingestion |
| Job State | Local Redis | Self-hosted ingestion lock + progress stream bridge for SSE, currently expected as a local host service |
| Graph Visualization | `@react-sigma/core` + Graphology + `@react-sigma/layout-forceatlas2` | React-friendly WebGL graph rendering with a dedicated graph data layer and ForceAtlas2 layout for knowledge-graph exploration |
| Frontend | React + Vite + TailwindCSS | Component-based UI |
| Local Infra | Dedicated Docker Compose files for Neo4j and Qdrant | `backend/neo4j/docker-compose.yml` and `backend/qdrant/docker-compose.yml`; MongoDB and Redis run as local host services |

---

## 3. Ingestion Pipeline (LangGraph)

The ingestion pipeline is a LangGraph graph that runs as a FastAPI `BackgroundTask` after a story is uploaded. It processes the document end-to-end, writes the normalized knowledge graph to local Neo4j, writes chunk embeddings to local Qdrant, stores story metadata in local MongoDB, and uses local Redis for ingestion status + SSE progress streaming.

### 3.1 Ingestion State Schema

```python
from typing import TypedDict, Optional

class IngestionState(TypedDict):
    story_id: str                      # unique ID for this story (= job_id)
    title: str                         # filename or user-provided title
    raw_text: str                      # full extracted text from the uploaded file
    graph_chunks: list[dict]           # large chunks for graph extraction + gleaning
    vector_chunks: list[dict]          # smaller retrieval chunks for Qdrant
    graph_docs: list                   # raw output from LLMGraphTransformer (nodes + relationships)
    alias_map: dict[str, str]          # deduplication map e.g. {"Sherlock": "Holmes"}
    graph_built: bool                  # True once Neo4j write is complete
    vectors_stored: bool               # True once Qdrant upsert is complete
    progress: list[str]                # log of steps for SSE streaming
```

### 3.2 Ingestion Nodes

#### Document Loader Node
- Accepts the uploaded file path
- Extracts raw text from `.pdf` (using `pypdf`) or `.txt`
- Builds two chunk streams from the same `raw_text` using `RecursiveCharacterTextSplitter` — no LLM involved at this stage
- Graph chunks use `GRAPH_CHUNK_SIZE=9000` and `GRAPH_CHUNK_OVERLAP=1000`
- Vector chunks use `VECTOR_CHUNK_SIZE=600` and `VECTOR_CHUNK_OVERLAP=100`
- Wraps each chunk as a LangChain `Document` with metadata: `story_id`, `chunk_id`, `chunk_index`, and `chunk_kind`

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

def document_loader_node(state: IngestionState) -> dict:
    graph_splitter = RecursiveCharacterTextSplitter(
        chunk_size=9000,
        chunk_overlap=1000,
    )
    vector_splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=100,
    )

    graph_chunks = [
        Document(
            page_content=chunk,
            metadata={
                "story_id": state["story_id"],
                "chunk_id": f"{state['story_id']}_graph_chunk_{i}",
                "chunk_index": i,
                "chunk_kind": "graph",
            }
        )
        for i, chunk in enumerate(graph_splitter.split_text(state["raw_text"]))
    ]

    vector_chunks = [
        Document(
            page_content=chunk,
            metadata={
                "story_id": state["story_id"],
                "chunk_id": f"{state['story_id']}_chunk_{i}",
                "chunk_index": i,
                "chunk_kind": "vector",
            }
        )
        for i, chunk in enumerate(vector_splitter.split_text(state["raw_text"]))
    ]

    return {
        "graph_chunks": graph_chunks,
        "vector_chunks": vector_chunks,
        "progress": state["progress"]
        + [f"✓ Built {len(graph_chunks)} graph chunks and {len(vector_chunks)} vector chunks"],
    }
```

#### Graph Extractor Node
- Passes the large `graph_chunks` to `LLMGraphTransformer` in a **single async batched call**
- `LLMGraphTransformer` extracts **both nodes and relationships** together — no separate entity or relationship extraction steps needed
- `allowed_nodes`, `allowed_relationships`, and `node_properties` are always passed to keep the graph consistent and queryable

```python
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite-preview",
    temperature=0,
)

transformer = LLMGraphTransformer(
    llm=llm,
    allowed_nodes=["CHARACTER", "PLACE", "EVENT", "OBJECT", "THEME"],
    allowed_relationships=[
        "FRIENDS_WITH", "ENEMY_OF", "LOVES", "BETRAYED",
        "KILLED", "PRESENT_AT", "CAUSED", "LOCATED_IN", "LOYAL_TO"
    ],
    node_properties=["description"],
    relationship_properties=["description"]
)

async def graph_extractor_node(state: IngestionState) -> dict:
    # Single async batched call — returns nodes + relationships per chunk
    graph_docs = await transformer.aconvert_to_graph_documents(state["graph_chunks"])

    return {
        "graph_docs": graph_docs,
        "progress": state["progress"]
        + [f"✓ Extracted graph from {len(state['graph_chunks'])} graph chunks"]
    }
```

#### Gleaning Node
- Runs a second LLM pass per graph chunk
- Builds a contextual prompt that includes the nodes and relationships already extracted from that exact graph chunk
- Asks for only genuinely new entities and relationships that are explicitly present in the text
- Merges the second-pass result with code-level node and relationship deduplication instead of trusting the prompt alone

```python
async def gleaning_node(state: IngestionState) -> dict:
    merged = []
    for chunk, original_doc in zip(state["graph_chunks"], state["graph_docs"], strict=False):
        existing_graph_context = format_existing_graph_context(original_doc)
        transformer_glean = build_contextual_gleaning_transformer(
            settings,
            llm,
            existing_graph_context,
        )
        gleaned_doc = await transformer_glean.aprocess_response(chunk)
        merged.append(merge_graph_documents(original_doc, gleaned_doc))

    return {
        "graph_docs": merged,
        "progress": state["progress"] + ["✓ Gleaning pass complete"]
    }
```

#### Deduplication Node
- Collects all unique node names extracted across all chunks
- Makes a **single LLM call** using LangChain Structured Output to group aliases
- Builds an `alias_map` — e.g. `{"Sherlock": "Holmes", "Mr. Holmes": "Holmes", "the detective": "Holmes"}`
- Applies the map to every node `id` and relationship `source`/`target` in `graph_docs` before writing to Neo4j
- Runs a second code-level graph deduplication pass after alias rewrite so canonicalization cannot create duplicate edges

```python
from pydantic import BaseModel, Field

class DuplicateGroup(BaseModel):
    canonical_name: str
    aliases: list[str]

class DeduplicationOutput(BaseModel):
    groups: list[DuplicateGroup]

dedup_llm = llm.with_structured_output(DeduplicationOutput)

async def deduplication_node(state: IngestionState) -> dict:
    all_names = list(set(
        node.id
        for doc in state["graph_docs"]
        for node in doc.nodes
    ))

    result: DeduplicationOutput = dedup_llm.invoke(f"""
        These names were extracted from a story.
        Group any names that refer to the same character or entity.
        Pick the most complete/formal name as the canonical name.

        Names: {all_names}
    """)

    # Build alias lookup map
    alias_map = {}
    for group in result.groups:
        for alias in group.aliases:
            alias_map[alias] = group.canonical_name

    # Apply map to all nodes and relationship endpoints in graph_docs
    for doc in state["graph_docs"]:
        for node in doc.nodes:
            node.id = alias_map.get(node.id, node.id)
        for rel in doc.relationships:
            rel.source.id = alias_map.get(rel.source.id, rel.source.id)
            rel.target.id = alias_map.get(rel.target.id, rel.target.id)

    deduplicated_docs = [deduplicate_graph_document(doc) for doc in state["graph_docs"]]

    return {
        "graph_docs": deduplicated_docs,
        "alias_map": alias_map,
        "progress": state["progress"] + [f"✓ Deduplicated {len(alias_map)} aliases"]
    }
```

#### Graph Builder Node
- Writes all normalized nodes and relationships from `graph_docs` to local Neo4j using the async driver
- Uses `MERGE` so canonical entities and relationships collapse cleanly per `story_id`
- Creates indexes on `name` and `type` for fast Cypher lookups
- Neo4j stores the graph structure only; no embeddings are stored there

```python
from neo4j import AsyncGraphDatabase

async def graph_builder_node(state: IngestionState) -> dict:
    async with AsyncGraphDatabase.driver(NEO4J_URL, auth=(NEO4J_USER, NEO4J_PASS)) as driver:
        async with driver.session() as session:
            for doc in state["graph_docs"]:
                for node in doc.nodes:
                    await session.run("""
                        MERGE (e:Entity {name: $name, story_id: $story_id})
                        SET e.type = $type, e.description = $description
                    """, name=node.id, story_id=state["story_id"],
                         type=node.type, description=node.properties.get("description", ""))

                for rel in doc.relationships:
                    await session.run(f"""
                        MATCH (a:Entity {{name: $source, story_id: $story_id}})
                        MATCH (b:Entity {{name: $target, story_id: $story_id}})
                        MERGE (a)-[r:{rel.type}]->(b)
                        SET r.description = $description
                    """, source=rel.source.id, target=rel.target.id,
                         story_id=state["story_id"],
                         description=rel.properties.get("description", ""))

    return {
        "graph_built": True,
        "progress": state["progress"] + ["✓ Knowledge graph written to local Neo4j"]
    }
```

#### Vector Embedder Node
- Embeds the smaller `vector_chunks` with local `BAAI/bge-small-en-v1.5`
- Upserts vector chunks and vectors into a local Qdrant collection named `story_{story_id}`
- Stores vector chunk metadata alongside vectors for cited retrieval
- Infers the collection vector size from the active embedding model before collection creation
- **This is the only place document embeddings are created** in the ingestion pipeline

```python
from langchain_community.embeddings import HuggingFaceBgeEmbeddings

async def vector_embedder_node(state: IngestionState) -> dict:
    texts = [c.page_content for c in state["vector_chunks"]]
    embeddings_model = HuggingFaceBgeEmbeddings(
        model_name="BAAI/bge-small-en-v1.5",
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
    embeddings = await embeddings_model.aembed_documents(texts)
    vector_size = len(await embeddings_model.aembed_query("vector size probe"))

    qdrant.create_collection(
        collection_name=f"story_{state['story_id']}",
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE)
    )

    points = [
        PointStruct(
            id=i,
            vector=embeddings[i],
            payload={
                "chunk_id": state["vector_chunks"][i].metadata["chunk_id"],
                "chunk_index": state["vector_chunks"][i].metadata["chunk_index"],
                "text": state["vector_chunks"][i].page_content,
                **state["vector_chunks"][i].metadata,
            }
        )
        for i in range(len(state["vector_chunks"]))
    ]
    qdrant.upsert(collection_name=f"story_{state['story_id']}", points=points)

    return {
        "vectors_stored": True,
        "progress": state["progress"]
        + [f"✓ {len(state['vector_chunks'])} vector chunks embedded into local Qdrant"]
    }
```

### 3.3 Ingestion Graph Wiring

```python
from langgraph.graph import StateGraph, END

builder = StateGraph(IngestionState)

builder.add_node("loader", document_loader_node)
builder.add_node("graph_extractor", graph_extractor_node)
builder.add_node("gleaning", gleaning_node)
builder.add_node("deduplication", deduplication_node)
builder.add_node("graph_builder", graph_builder_node)
builder.add_node("vector_embedder", vector_embedder_node)

builder.set_entry_point("loader")
builder.add_edge("loader", "graph_extractor")
builder.add_edge("graph_extractor", "gleaning")
builder.add_edge("gleaning", "deduplication")
builder.add_edge("deduplication", "graph_builder")
builder.add_edge("deduplication", "vector_embedder")   # runs in parallel with graph_builder
builder.add_edge("graph_builder", END)
builder.add_edge("vector_embedder", END)

ingestion_graph = builder.compile()
```

---

## 4. Query Agent (LangGraph)

The query agent is a separate LangGraph graph that handles user questions after a story has been ingested. Its primary job is to **route each question to the right retrieval method**, execute graph retrieval against local Neo4j and/or vector retrieval against local Qdrant, and synthesize a cited answer.

Conversation memory is enabled only for the query graph. Each `story_id` can have many chats, each chat has a `chat_id`, and `chat_id` is used as the LangGraph `thread_id`. The query graph is compiled with `MongoDBSaver`, so follow-up questions in the same chat can reuse prior messages and transcript state even after an app restart.

### 4.1 Query State Schema

```python
class QueryState(TypedDict):
    story_id: str
    question: str
    messages: list[BaseMessage]            # LangGraph message history for memory
    transcript: list[dict]                # structured chat transcript for frontend
    query_type: str                       # "vector" | "graph" | "hybrid"
    routing_reason: Optional[str]
    cypher_query: Optional[str]
    graph_results: Optional[list[dict]]
    vector_results: Optional[list[dict]]
    evidence: Optional[dict]
    answer: str
    citations: list[dict]                 # cited chunks and/or graph nodes/edges
```

### 4.2 Query Nodes

#### Router Node
- The first node — classifies the question into `vector`, `graph`, or `hybrid`
- Uses **LangChain Structured Output** to return a typed routing decision
- Receives recent chat history so it can route follow-up questions using prior conversational context

```python
class RouterOutput(BaseModel):
    query_type: str    # "vector" | "graph" | "hybrid"
    reasoning: str     # one-line explanation of the routing decision

router = llm.with_structured_output(RouterOutput)

def router_node(state: QueryState) -> dict:
    prompt = build_router_prompt(
        messages=state["messages"],
        history_limit=12,
    )
    result: RouterOutput = router.invoke(prompt)
    return {
        "query_type": result.query_type,
        "routing_reason": result.reasoning
    }
```

#### Cypher Generator Node (Graph path only)
- Translates the natural language question into a Neo4j Cypher query
- Uses **LangChain Structured Output** to produce a valid, typed Cypher string
- Scopes all queries to `story_id` to prevent cross-story contamination
- Receives recent message history so follow-up prompts like "What about him?" can still resolve the intended entity

```python
class CypherOutput(BaseModel):
    cypher: str   # valid Cypher query scoped to story_id

cypher_generator = llm.with_structured_output(CypherOutput)

def cypher_generator_node(state: QueryState) -> dict:
    prompt = build_cypher_prompt(
        story_id=state["story_id"],
        messages=state["messages"],
        allowed_relationships=ALLOWED_RELATIONSHIP_TYPES,
        history_limit=12,
    )
    result: CypherOutput = cypher_generator.invoke(prompt)
    return {"cypher_query": result.cypher}
```

#### Graph Retriever Node
- Executes the generated Cypher query against local Neo4j
- Returns matched nodes and relationships as structured dicts
- These become citations in the final answer

#### Vector Retriever Node
- Builds a contextualized search query from the current question plus recent transcript history
- Embeds that contextualized search query with the same local `BAAI/bge-small-en-v1.5` model used during ingestion and searches the local Qdrant collection for the selected story
- Returns the top 4 most relevant chunks with metadata
- These become text-based citations in the final answer

#### Answer Synthesizer Node
- Receives whichever results were retrieved (graph, vector, or both)
- Uses **LangChain Structured Output** to produce a typed answer with explicit citations
- Citations reference either `chunk_id` (for vector results) or `node_name + relationship` (for graph results)
- Receives recent message history so follow-up questions can be answered in context
- Appends an assistant message to LangGraph `messages` and a structured assistant transcript item to `transcript`
- The API layer persists chat metadata in MongoDB, while the full query-agent state is checkpointed automatically by LangGraph

```python
class Citation(BaseModel):
    type: str          # "chunk" | "graph_node" | "graph_edge"
    reference: str     # chunk_id, node name, or "NodeA -[REL]-> NodeB"
    excerpt: str       # the relevant text or relationship description

class AnswerOutput(BaseModel):
    answer: str
    citations: list[Citation]

answer_synthesizer = llm.with_structured_output(AnswerOutput)
```

### 4.3 Query Graph Wiring

```python
def route_query(state: QueryState) -> str:
    if state["query_type"] == "vector":
        return "vector_only"
    elif state["query_type"] == "graph":
        return "graph_only"
    else:
        return "hybrid"

builder = StateGraph(QueryState)

builder.add_node("router", router_node)
builder.add_node("cypher_generator", cypher_generator_node)
builder.add_node("graph_retriever", graph_retriever_node)
builder.add_node("vector_retriever", vector_retriever_node)
builder.add_node("answer_synthesizer", answer_synthesizer_node)

builder.set_entry_point("router")
builder.add_conditional_edges(
    "router",
    route_query,
    {
        "vector_only": "vector_retriever",
        "graph_only": "cypher_generator",
        "hybrid": "cypher_generator"
    }
)
builder.add_edge("cypher_generator", "graph_retriever")
builder.add_conditional_edges(
    "graph_retriever",
    lambda s: "vector_retriever" if s["query_type"] == "hybrid" else "answer_synthesizer",
    {
        "vector_retriever": "vector_retriever",
        "answer_synthesizer": "answer_synthesizer"
    }
)
builder.add_edge("vector_retriever", "answer_synthesizer")
builder.add_edge("answer_synthesizer", END)

query_graph = builder.compile(checkpointer=mongo_checkpointer)
```

Runtime compile and invocation pattern:

```python
mongo_checkpointer = MongoDBSaver(...)
query_graph = builder.compile(checkpointer=mongo_checkpointer)

result = await query_graph.ainvoke(
    initial_state,
    config={"configurable": {"thread_id": chat_id}},
)
```

---

## 5. LangChain Structured Output — Usage Policy

All typed LLM control outputs in this system **must** use LangChain's `.with_structured_output()`. No raw string parsing or ad-hoc JSON extraction is allowed for routing, deduplication, Cypher generation, or answer synthesis.

Nodes using structured output:

| Node | Pydantic Model | Purpose |
|---|---|---|
| Deduplication | `DeduplicationOutput` | Groups aliases into canonical names |
| Router | `RouterOutput` | Typed query classification |
| Cypher Generator | `CypherOutput` | Valid Cypher string scoped to `story_id` |
| Answer Synthesizer | `AnswerOutput` | Typed answer + citations |

`LLMGraphTransformer` is still used for graph extraction and contextual gleaning, but that path is handled through the transformer's own schema machinery rather than the project's explicit `.with_structured_output()` wrappers.

---

## 6. Backend API (FastAPI)

All endpoints are `async`. Ingestion runs as a `BackgroundTask`. The system accepts exactly one `.pdf` or `.txt` per ingestion request, and only one ingestion job may be active at any given time. Multiple previously ingested stories may remain stored for later selection at inference time. Neo4j and Qdrant are typically started from their dedicated Docker Compose files under `backend/`, while MongoDB and Redis are expected as local host services.

### 6.1 Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/stories` | Upload one story file (`.pdf` or `.txt`) — rejects the request if another ingestion job is already running; fires ingestion pipeline as BackgroundTask and returns `story_id` instantly |
| `GET` | `/api/stories/{story_id}/stream` | SSE stream of ingestion progress |
| `GET` | `/api/stories/{story_id}` | Get story status + metadata |
| `GET` | `/api/stories` | List all ingested stories for the selector/history sidebar, keyed by stored file name |
| `GET` | `/api/stories/{story_id}/graph` | Return all nodes and edges for the story (used by graph visualization) |
| `GET` | `/api/stories/{story_id}/chunks` | Return all stored chunks for the story in chunk order |
| `GET` | `/api/stories/{story_id}/chats` | List all chats for the selected story |
| `GET` | `/api/stories/{story_id}/chats/{chat_id}` | Get one chat summary for the selected story |
| `GET` | `/api/stories/{story_id}/chats/{chat_id}/messages` | Return the structured transcript for one chat |
| `POST` | `/api/stories/{story_id}/chats/messages` | Send a user message; if `chat_id` is omitted, create a new chat and use it as the LangGraph `thread_id` |
| `GET` | `/api/health` | Health check |

### 6.2 Key Endpoint Implementations

```python
@app.post("/api/stories", response_model=StoryResponse)
async def upload_story(
    file: UploadFile,
    background_tasks: BackgroundTasks
):
    story_id = str(uuid4())

    # Only one ingestion job may be active at a time
    if await redis.get("ingestion_lock") == "running":
        raise HTTPException(status_code=409, detail="Another story is currently being ingested")

    existing_story = await mongo.stories.find_one({"filename": file.filename})
    if existing_story:
        raise HTTPException(status_code=409, detail="A story with this file name already exists")

    # Save uploaded file to disk
    file_path = f"/tmp/{story_id}_{file.filename}"
    with open(file_path, "wb") as f:
        f.write(await file.read())

    # Initialize job in Redis
    await redis.hset(f"job:{story_id}", mapping={"status": "queued", "filename": file.filename})
    await redis.set("ingestion_lock", "running")

    # Fire ingestion pipeline in background — returns immediately
    background_tasks.add_task(
        run_ingestion,
        story_id=story_id,
        title=file.filename,
        file_path=file_path
    )

    return StoryResponse(story_id=story_id, status="queued")


@app.post("/api/stories/{story_id}/chats/messages")
async def send_story_chat_message(story_id: str, request: ChatMessageRequest):
    chat_id = request.chat_id or str(uuid4())
    created_new_chat = request.chat_id is None

    if not created_new_chat:
        await chat_service.get_chat(story_id, chat_id)

    result = await query_graph.ainvoke(
        {
            "story_id": story_id,
            "question": request.message,
            "messages": [HumanMessage(content=request.message)],
            "transcript": [build_user_transcript(request.message)],
            "query_type": "",
            "routing_reason": None,
            "cypher_query": None,
            "graph_results": None,
            "vector_results": None,
            "evidence": None,
            "answer": "",
            "citations": [],
        },
        config={"configurable": {"thread_id": chat_id}},
    )

    if created_new_chat:
        await chat_service.create_chat(story_id, chat_id, request.message)

    await chat_service.update_chat_after_turn(
        story_id,
        chat_id,
        user_message=request.message,
        answer=result["answer"],
        turn_count=count_assistant_turns(result.get("transcript")),
    )

    return {
        "chat_id": chat_id,
        "story_id": story_id,
        "created_new_chat": created_new_chat,
        "answer": result["answer"],
        "query_type": result["query_type"],
        "routing_reason": result.get("routing_reason"),
        "citations": result["citations"],
        "evidence": result.get("evidence"),
    }
```

Inference-time document selection flow:
- Frontend calls `GET /api/stories`
- User selects a stored PDF/TXT by its `title` / `filename`
- Frontend resolves that selection to the corresponding `story_id`
- Frontend calls `GET /api/stories/{story_id}/chats` to list prior chats for that story
- User either opens an existing `chat_id` or sends the first message without a `chat_id`
- All graph, chunks, and chat-message requests are then sent for that chosen `story_id`

### 6.3 Ingestion SSE — Redis-backed progress events

```python
async def run_ingestion(story_id: str, title: str, file_path: str):
    await redis.hset(f"job:{story_id}", "status", "running")

    async for update in ingestion_graph.astream(
        {"story_id": story_id, "title": title, "file_path": file_path, ...},
        stream_mode="updates"
    ):
        node_name = list(update.keys())[0]
        node_output = update[node_name]

        await redis.rpush(f"stream:{story_id}", json.dumps({
            "node": node_name,
            "progress": node_output.get("progress", [])[-1]
        }))

    # Save story to MongoDB, then mark complete in Redis
    await save_story(story_id, title)
    await redis.hset(f"job:{story_id}", "status", "complete")
    await redis.delete("ingestion_lock")
```

---

## 7. MongoDB — Story, Chat, and Checkpoint Store

### 7.1 Collections

**`stories` collection** — one document per ingested story:

```python
{
    "_id": "story_id",
    "title": "Sherlock Holmes - A Study in Scarlet",
    "filename": "study_in_scarlet.pdf",
    "display_name": "study_in_scarlet.pdf",
    "status": "complete",
    "entity_count": 47,
    "relationship_count": 89,
    "chunk_count": 120,
    "created_at": "2026-03-18T10:00:00Z"
}
```

**`chats` collection** — one document per story-scoped chat:

```python
{
    "_id": "chat_id",
    "chat_id": "chat_id",
    "thread_id": "chat_id",
    "story_id": "story_id",
    "title": "Who are Holmes's enemies?",
    "created_at": "2026-03-18T10:05:00Z",
    "updated_at": "2026-03-18T10:07:00Z",
    "turn_count": 2,
    "last_user_message": "What about his allies?",
    "last_answer_preview": "Holmes's closest ally is Watson..."
}
```

**LangGraph checkpoint collections** — persisted query-agent state:

```python
langgraph_checkpoints
langgraph_checkpoint_writes
```

Storage and selection rules:
- `filename` / `display_name` is the user-facing selector value for each stored PDF/TXT
- file names must be unique across stored stories; if a duplicate name is uploaded, the backend should reject it or require the user to rename the file first
- `story_id` remains the internal primary key used by the API and data stores
- each `story_id` can have many `chat_id` values
- `chat_id` is also the LangGraph `thread_id`
- Neo4j stores graph entities/relationships, Qdrant stores chunk vectors, and Redis stores transient ingestion lock + progress events
- each assistant transcript item also stores `routing_reason` so the frontend can explain why graph, vector, or hybrid retrieval was chosen
- graph answers persist the nodes, relationships, and normalized raw graph results used for the answer
- vector answers persist `chunk_ids` and chunk payloads used for the answer
- hybrid answers persist both graph and vector evidence together

### 7.2 Write Points

- **`save_story()`** — called after ingestion completes; inserts story document with entity/relationship/chunk counts and the stored file name used for future selection
- **`create_chat()`** — called after the first message in a new chat; inserts chat summary metadata into `chats`
- **`update_chat_after_turn()`** — called after every assistant response; updates `updated_at`, `turn_count`, and last-message previews
- **LangGraph `MongoDBSaver`** — automatically persists full query-agent state for each `thread_id` into the checkpoint collections

### 7.3 History Endpoints Data Flow

`GET /api/stories` → lean projection (`_id`, `title`, `filename`, `display_name`, `status`, `created_at`, `entity_count`) → sidebar list / document selector by name

`GET /api/stories/{story_id}/chats` → chat summaries for the selected story → chat sidebar / resume list

`GET /api/stories/{story_id}/chats/{chat_id}/messages` → latest transcript snapshot for that thread → chat transcript panel with citations, routing reasons, and stored retrieval evidence

`GET /api/stories/{story_id}/chunks` → ordered chunk list from Qdrant → chunk browser / evidence inspection panel

---

## 8. Graph Visualization (Frontend)

The interactive graph is rendered using `@react-sigma/core` on top of Graphology. Graphology acts as the frontend graph data layer, Sigma.js provides WebGL rendering, and `@react-sigma/layout-forceatlas2` is used for the default knowledge-graph layout. The user first selects a stored PDF/TXT by name, then the frontend calls `GET /api/stories/{story_id}/graph` for that selected document, loads the returned nodes and edges into a Graphology graph, and renders the result through Sigma. The frontend can also call `GET /api/stories/{story_id}/chunks` to show the chunk corpus for the same story, and can render `routing_reason` plus persisted retrieval evidence from the chat transcript endpoints.

Why this stack is preferred for Story GraphRAG:
- WebGL rendering remains responsive for dense story graphs with hundreds of nodes and edges
- Graphology provides a proper graph data model with node/edge attributes instead of treating the graph as a flat render payload only
- ForceAtlas2 gives a more professional knowledge-graph layout than a generic force-graph setup and leaves room for future graph metrics or search utilities

**Node styling by entity type:**

| Entity Type | Color |
|---|---|
| CHARACTER | Blue |
| PLACE | Green |
| EVENT | Orange |
| OBJECT | Purple |
| THEME | Gray |

**Interaction:**
- Hover a node → show entity name + description tooltip
- Click a node → highlight all directly connected nodes and edges
- Click an edge → show relationship description
- Click "Deep Dive" on a node → ask the query agent for a full AI-generated summary of that character or event

---

## 9. Project Structure

```
story-graphrag/
├── backend/
│   ├── main.py                        # FastAPI app factory + lifespan bootstrap
│   ├── create_index.py                # Startup index creation for story/chat MongoDB + Neo4j
│   ├── pyproject.toml
│   ├── .env.example
│   ├── neo4j/
│   │   └── docker-compose.yml         # Local Neo4j runner
│   ├── qdrant/
│   │   └── docker-compose.yml         # Local Qdrant runner
│   ├── app/
│   │   ├── core/
│   │   │   ├── config.py              # Settings / env parsing
│   │   │   ├── database.py            # MongoDB, Redis, Neo4j, Qdrant, and checkpointer startup/shutdown
│   │   │   ├── llm_config.py          # Gemini + BGE providers + structured-output wrappers
│   │   │   ├── logging.py             # Request context + logging config
│   │   │   ├── dependencies.py
│   │   │   ├── exceptions.py
│   │   │   └── constants.py
│   │   ├── graph_rag_agent/
│   │   │   ├── ingestion/
│   │   │   │   ├── graph.py           # Ingestion LangGraph definition + merge/dedup helpers
│   │   │   │   ├── prompts.py
│   │   │   │   └── state.py
│   │   │   └── query/
│   │   │       ├── graph.py           # Query LangGraph definition
│   │   │       ├── prompts.py
│   │   │       └── state.py
│   │   ├── routers/
│   │   │   ├── health.py
│   │   │   └── stories.py
│   │   ├── schemas/
│   │   │   ├── common.py
│   │   │   ├── graph.py
│   │   │   ├── query.py
│   │   │   └── story.py
│   │   └── services/
│   │       ├── container.py
│   │       ├── chat_service.py
│   │       ├── file_service.py
│   │       ├── graph_service.py
│   │       ├── job_service.py
│   │       ├── story_service.py
│   │       └── vector_service.py
│   └── tests/
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   └── components/
│   │       ├── UploadPanel.jsx        # File upload + ingestion progress
│   │       ├── GraphVisualization.jsx # Sigma.js + Graphology rendering
│   │       ├── QueryInterface.jsx     # Chat input + answer display
│   │       ├── CitationPanel.jsx      # Cited chunks and graph nodes
│   │       ├── HistorySidebar.jsx     # Past stories list
│   │       ├── ChatSidebar.jsx        # Past chats for current story
│   │       └── ChatTranscript.jsx     # Chat transcript for current story/chat
│   ├── package.json
│   └── vite.config.js
├── documentation/
└── README.md
```

---

## 10. Environment Variables

```env
GOOGLE_API_KEY=
GOOGLE_CHAT_MODEL=gemini-3.1-flash-lite-preview
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_DEVICE=cpu
EMBEDDING_NORMALIZE=true

# Local host setup defaults
NEO4J_URL=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASS=password
QDRANT_URL=http://localhost:6333
REDIS_URL=redis://localhost:6379
MONGODB_URL=mongodb://localhost:27017
MONGODB_DB=story_graphrag
CHECKPOINT_DB=
CHECKPOINT_COLLECTION_NAME=langgraph_checkpoints
CHECKPOINT_WRITES_COLLECTION_NAME=langgraph_checkpoint_writes
UPLOAD_DIR=/tmp/story_graphrag_uploads
CORS_ORIGINS=*
CHAT_TITLE_MAX_LENGTH=80
CHAT_PREVIEW_MAX_LENGTH=120
CHAT_PROMPT_HISTORY_MESSAGES=12
INFRASTRUCTURE_TIMEOUT_SECONDS=2
```

Neo4j and Qdrant can be started from the compose files in `backend/neo4j` and `backend/qdrant`. MongoDB and Redis are expected to be running locally on their default ports.

---

## 11. Docker Compose

Current local infra files shipped in the repository:

- `backend/neo4j/docker-compose.yml` — local Neo4j with ports `7474` and `7687`, persistent volume, and healthcheck
- `backend/qdrant/docker-compose.yml` — local Qdrant with ports `6333` and `6334`, persistent volume, and healthcheck

Current runtime expectation:

- Neo4j runs from the dedicated Docker Compose file under `backend/neo4j`
- Qdrant runs from the dedicated Docker Compose file under `backend/qdrant`
- MongoDB runs as a local host service at `localhost:27017`
- Redis runs as a local host service at `localhost:6379`
