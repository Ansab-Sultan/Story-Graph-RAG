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
│     [Upload] [Graph Viz] [Q&A Interface] [History Sidebar]    │
└────────────────────────┬─────────────────────────────────────┘
                         │ HTTP / SSE
┌────────────────────────▼─────────────────────────────────────┐
│                    FastAPI Backend                             │
│         (Async REST API + SSE Streaming Endpoints)            │
└──────┬──────────────────────┬────────────────────────────────┘
       │                      │
┌──────▼──────┐      ┌────────▼────────┐
│  Ingestion  │      │   Query Agent   │
│  Pipeline   │      │  (LangGraph)    │
│ (LangGraph) │      │                 │
└──────┬──────┘      └────────┬────────┘
       │                      │
  ┌────▼──────────────────────▼────┐
  │        Local Data Layer         │
  │ Neo4j │ Qdrant │ MongoDB │     │
  └─────────────────────────────────┘
       │                      │
  OpenAI API           Redis (local job bus)
```

---

## 2. Tech Stack

| Layer | Technology | Reason |
|---|---|---|
| Agent Framework | LangGraph | Stateful graph execution for both ingestion pipeline and query routing agent |
| LLM | OpenAI GPT-4o-mini | Graph extraction, deduplication, answer generation |
| Graph Extraction | LangChain `LLMGraphTransformer` | Extracts nodes + relationships together in one async batched call using function calling |
| Text Splitting | LangChain `RecursiveCharacterTextSplitter` | Pure text chunking — no LLM, 600 tokens, 100 overlap |
| Structured Output | LangChain `.with_structured_output()` | Type-safe responses for deduplication, routing, Cypher generation, and answer synthesis |
| Graph Database | Local Neo4j | Self-hosted graph storage and Cypher traversal on the developer machine |
| Vector Database | Local Qdrant | Self-hosted semantic similarity search for chunk retrieval, typically via Docker Compose |
| History Store | Local MongoDB (Motor async driver) | Self-hosted persistence for stories, file-name based selection, and Q&A history |
| Embeddings | OpenAI text-embedding-3-small | Chunk embeddings stored in Qdrant only |
| Backend | FastAPI (fully async) | Async endpoints, SSE streaming, BackgroundTasks for ingestion |
| Job State | Local Redis | Self-hosted ingestion lock + progress stream bridge for SSE |
| Graph Visualization | react-force-graph | Interactive force-directed graph rendering in the browser |
| Frontend | React + Vite + TailwindCSS | Component-based UI |
| Containerization | Docker + Docker Compose | Single-command local setup for backend, frontend, Neo4j, Qdrant, Redis, and MongoDB |

---

## 3. Ingestion Pipeline (LangGraph)

The ingestion pipeline is a LangGraph graph that runs as a FastAPI `BackgroundTask` after a story is uploaded. It processes the document end-to-end, writes the normalized knowledge graph to local Neo4j, writes chunk embeddings to local Qdrant, stores story metadata and Q&A history in local MongoDB, and uses local Redis for ingestion status + SSE progress streaming.

### 3.1 Ingestion State Schema

```python
from typing import TypedDict, Optional

class IngestionState(TypedDict):
    story_id: str                      # unique ID for this story (= job_id)
    title: str                         # filename or user-provided title
    raw_text: str                      # full extracted text from the uploaded file
    chunks: list[dict]                 # text chunks with metadata (600 tokens, 100 overlap)
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
- Uses `RecursiveCharacterTextSplitter` with **600 tokens, 100-token overlap** — no LLM involved at this stage
- Wraps each chunk as a LangChain `Document` with metadata: `story_id`, `chunk_id`, `chunk_index`, `page_number`

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

def document_loader_node(state: IngestionState) -> dict:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=100
    )
    raw_chunks = splitter.split_text(state["raw_text"])

    chunks = [
        Document(
            page_content=chunk,
            metadata={
                "story_id": state["story_id"],
                "chunk_id": f"{state['story_id']}_chunk_{i}",
                "chunk_index": i
            }
        )
        for i, chunk in enumerate(raw_chunks)
    ]

    return {
        "chunks": chunks,
        "progress": state["progress"] + [f"✓ Split into {len(chunks)} chunks"]
    }
```

#### Graph Extractor Node
- Passes all LangChain `Document` chunks to `LLMGraphTransformer` in a **single async batched call**
- `LLMGraphTransformer` extracts **both nodes and relationships** together — no separate entity or relationship extraction steps needed
- `allowed_nodes`, `allowed_relationships`, and `node_properties` are always passed to keep the graph consistent and queryable

```python
from langchain_experimental.graph_transformers import LLMGraphTransformer
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(temperature=0, model="gpt-4o-mini")

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
    graph_docs = await transformer.aconvert_to_graph_documents(state["chunks"])

    return {
        "graph_docs": graph_docs,
        "progress": state["progress"] + [f"✓ Extracted graph from {len(state['chunks'])} chunks"]
    }
```

#### Gleaning Node
- Runs a second LLM pass over each chunk asking "what entities or relationships were missed?"
- Merges any newly found nodes and relationships back into `graph_docs`
- Uses the same `LLMGraphTransformer` — one additional call per chunk, diminishing returns after one pass

```python
async def gleaning_node(state: IngestionState) -> dict:
    gleaning_prompt = (
        "Review the story excerpt again carefully. "
        "Identify any characters, places, events, or relationships that were missed in the first pass. "
        "Only return NEW entities and relationships not already found."
    )

    transformer_glean = LLMGraphTransformer(
        llm=llm,
        allowed_nodes=["CHARACTER", "PLACE", "EVENT", "OBJECT", "THEME"],
        allowed_relationships=[
            "FRIENDS_WITH", "ENEMY_OF", "LOVES", "BETRAYED",
            "KILLED", "PRESENT_AT", "CAUSED", "LOCATED_IN", "LOYAL_TO"
        ],
        node_properties=["description"],
        relationship_properties=["description"],
        additional_instructions=gleaning_prompt
    )

    gleaned_docs = await transformer_glean.aconvert_to_graph_documents(state["chunks"])

    # Merge gleaned nodes and relationships into existing graph_docs
    merged = list(state["graph_docs"])
    for orig, glean in zip(merged, gleaned_docs):
        existing_node_ids = {n.id for n in orig.nodes}
        for node in glean.nodes:
            if node.id not in existing_node_ids:
                orig.nodes.append(node)
        orig.relationships.extend(glean.relationships)

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
- Neo4j `MERGE` then collapses canonical entities cleanly for each `story_id`

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

    return {
        "graph_docs": state["graph_docs"],
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
- Embeds the raw text chunks in a single batched OpenAI API call
- Upserts chunks and vectors into a local Qdrant collection named `story_{story_id}`
- Stores chunk metadata alongside vectors for cited retrieval
- **This is the only place embeddings are created** in the ingestion pipeline

```python
async def vector_embedder_node(state: IngestionState) -> dict:
    texts = [c.page_content for c in state["chunks"]]
    embeddings = openai_client.embeddings.create(
        input=texts, model="text-embedding-3-small"
    ).data

    qdrant.create_collection(
        collection_name=f"story_{state['story_id']}",
        vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
    )

    points = [
        PointStruct(
            id=i,
            vector=embeddings[i].embedding,
            payload={
                "chunk_id": state["chunks"][i].metadata["chunk_id"],
                "chunk_index": state["chunks"][i].metadata["chunk_index"],
                "text": state["chunks"][i].page_content,
                **state["chunks"][i].metadata,
            }
        )
        for i in range(len(state["chunks"]))
    ]
    qdrant.upsert(collection_name=f"story_{state['story_id']}", points=points)

    return {
        "vectors_stored": True,
        "progress": state["progress"] + [f"✓ {len(state['chunks'])} chunks embedded into local Qdrant"]
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

### 4.1 Query State Schema

```python
class QueryState(TypedDict):
    story_id: str
    question: str
    query_type: str           # "vector" | "graph" | "hybrid"
    cypher_query: Optional[str]
    graph_results: Optional[list[dict]]
    vector_results: Optional[list[dict]]
    answer: str
    citations: list[dict]     # cited chunks and/or graph nodes/edges
```

### 4.2 Query Nodes

#### Router Node
- The first node — classifies the question into `vector`, `graph`, or `hybrid`
- Uses **LangChain Structured Output** to return a typed routing decision

```python
class RouterOutput(BaseModel):
    query_type: str    # "vector" | "graph" | "hybrid"
    reasoning: str     # one-line explanation of the routing decision

router = llm.with_structured_output(RouterOutput)

def router_node(state: QueryState) -> dict:
    prompt = f"""
    Classify this question about a story into one of three retrieval types:

    - "vector": factual, descriptive, or thematic questions answerable from text passages
    - "graph": questions about relationships, connections, or multi-hop reasoning between characters/events
    - "hybrid": questions that require both text passages AND relationship traversal

    Question: {state['question']}
    """
    result: RouterOutput = router.invoke(prompt)
    return {"query_type": result.query_type}
```

#### Cypher Generator Node (Graph path only)
- Translates the natural language question into a Neo4j Cypher query
- Uses **LangChain Structured Output** to produce a valid, typed Cypher string
- Scopes all queries to `story_id` to prevent cross-story contamination

```python
class CypherOutput(BaseModel):
    cypher: str   # valid Cypher query scoped to story_id

cypher_generator = llm.with_structured_output(CypherOutput)

def cypher_generator_node(state: QueryState) -> dict:
    prompt = f"""
    Generate a Neo4j Cypher query to answer the following question.
    All nodes have a story_id property — always filter by: story_id = '{state['story_id']}'

    Available node types: Entity (with .type = CHARACTER | PLACE | EVENT | OBJECT | THEME)
    Available relationship types: FRIENDS_WITH, ENEMY_OF, LOVES, BETRAYED, KILLED,
    PRESENT_AT, CAUSED, LOCATED_IN, OWNS, MEMBER_OF, LOYAL_TO

    Question: {state['question']}
    """
    result: CypherOutput = cypher_generator.invoke(prompt)
    return {"cypher_query": result.cypher}
```

#### Graph Retriever Node
- Executes the generated Cypher query against local Neo4j
- Returns matched nodes and relationships as structured dicts
- These become citations in the final answer

#### Vector Retriever Node
- Embeds the question and searches the local Qdrant collection for the selected story
- Returns the top 4 most relevant chunks with metadata
- These become text-based citations in the final answer

#### Answer Synthesizer Node
- Receives whichever results were retrieved (graph, vector, or both)
- Uses **LangChain Structured Output** to produce a typed answer with explicit citations
- Citations reference either `chunk_id` (for vector results) or `node_name + relationship` (for graph results)

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

query_graph = builder.compile()
```

---

## 5. LangChain Structured Output — Usage Policy

All LLM calls in this system **must** use LangChain's `.with_structured_output()`. No raw string parsing or JSON extraction anywhere.

Nodes using structured output:

| Node | Pydantic Model | Purpose |
|---|---|---|
| Gleaning | `LLMGraphTransformer` (built-in) | Second-pass extraction of missed entities/relationships |
| Deduplication | `DeduplicationOutput` | Groups aliases into canonical names |
| Router | `RouterOutput` | Typed query classification |
| Cypher Generator | `CypherOutput` | Valid Cypher string scoped to `story_id` |
| Answer Synthesizer | `AnswerOutput` | Typed answer + citations |

---

## 6. Backend API (FastAPI)

All endpoints are `async`. Ingestion runs as a `BackgroundTask`. The system accepts exactly one `.pdf` or `.txt` per ingestion request, and only one ingestion job may be active at any given time. Multiple previously ingested stories may remain stored for later selection at inference time. Neo4j, Qdrant, MongoDB, and Redis are all expected to run locally, with Docker Compose as the default setup.

### 6.1 Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/stories` | Upload one story file (`.pdf` or `.txt`) — rejects the request if another ingestion job is already running; fires ingestion pipeline as BackgroundTask and returns `story_id` instantly |
| `GET` | `/api/stories/{story_id}/stream` | SSE stream of ingestion progress |
| `GET` | `/api/stories/{story_id}` | Get story status + metadata |
| `GET` | `/api/stories/{story_id}/graph` | Return all nodes and edges for the story (used by graph visualization) |
| `POST` | `/api/stories/{story_id}/query` | Ask a question about the selected story, returns answer + citations |
| `GET` | `/api/stories` | List all ingested stories for the selector/history sidebar, keyed by stored file name |
| `GET` | `/api/stories/{story_id}/qa` | Get all past Q&A for a story |
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


@app.post("/api/stories/{story_id}/query")
async def query_story(story_id: str, request: QueryRequest):
    result = await query_graph.ainvoke({
        "story_id": story_id,
        "question": request.question,
        "query_type": "",
        "graph_results": None,
        "vector_results": None,
        "answer": "",
        "citations": []
    })

    # Persist Q&A to MongoDB
    await save_qa(story_id, request.question, result["answer"], result["citations"])

    return {"answer": result["answer"], "citations": result["citations"]}
```

Inference-time document selection flow:
- Frontend calls `GET /api/stories`
- User selects a stored PDF/TXT by its `title` / `filename`
- Frontend resolves that selection to the corresponding `story_id`
- All graph and query requests are then sent for that chosen `story_id`

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

## 7. MongoDB — History Store

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
    "created_at": "2026-03-18T10:00:00Z",
    "qa": [
        {
            "question": "Who are Holmes's enemies?",
            "answer": "Holmes's primary enemies include...",
            "citations": [...],
            "query_type": "graph",
            "asked_at": "2026-03-18T10:05:00Z"
        }
    ]
}
```

Storage and selection rules:
- `filename` / `display_name` is the user-facing selector value for each stored PDF/TXT
- file names must be unique across stored stories; if a duplicate name is uploaded, the backend should reject it or require the user to rename the file first
- `story_id` remains the internal primary key used by the API and data stores
- Neo4j stores graph entities/relationships, Qdrant stores chunk vectors, and Redis stores transient ingestion lock + progress events

### 7.2 Write Points

- **`save_story()`** — called after ingestion completes; inserts story document with entity/relationship/chunk counts and the stored file name used for future selection
- **`save_qa()`** — called after every query; uses `$push` to append Q&A pair to `qa` array

### 7.3 History Endpoints Data Flow

`GET /api/stories` → lean projection (`_id`, `title`, `filename`, `display_name`, `status`, `created_at`, `entity_count`) → sidebar list / document selector by name

`GET /api/stories/{story_id}/qa` → full `qa` array for a story → Q&A history panel

---

## 8. Graph Visualization (Frontend)

The interactive graph is rendered using `react-force-graph-2d`. The user first selects a stored PDF/TXT by name, then the frontend calls `GET /api/stories/{story_id}/graph` for that selected document and renders all entities as nodes and all relationships as labeled edges.

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
│   ├── main.py                        # FastAPI app entrypoint
│   ├── api/
│   │   └── routes.py                  # All API route handlers
│   ├── ingestion/
│   │   ├── graph.py                   # Ingestion LangGraph definition + wiring
│   │   ├── state.py                   # IngestionState TypedDict
│   │   └── nodes/
│   │       ├── loader.py              # RecursiveCharacterTextSplitter + LangChain Document wrapping
│   │       ├── graph_extractor.py     # LLMGraphTransformer — extracts nodes + relationships together
│   │       ├── gleaning.py            # Second-pass LLMGraphTransformer with additional_instructions
│   │       ├── deduplication.py       # Alias grouping with structured output → builds alias_map
│   │       ├── graph_builder.py       # Neo4j entity + relationship writes
│   │       └── vector_embedder.py     # Qdrant chunk vector upserts
│   ├── query/
│   │   ├── graph.py                   # Query LangGraph definition
│   │   ├── state.py                   # QueryState TypedDict
│   │   └── nodes/
│   │       ├── router.py              # Query type classifier (vector | graph | hybrid)
│   │       ├── cypher_generator.py    # NL → Cypher via structured output
│   │       ├── graph_retriever.py     # Neo4j Cypher execution
│   │       ├── vector_retriever.py    # Qdrant similarity search
│   │       └── answer_synthesizer.py  # Final answer + citations via structured output
│   ├── db/
│   │   ├── mongo.py                   # AsyncIOMotorClient setup for local MongoDB
│   │   ├── neo4j.py                   # Async Neo4j driver setup for local Neo4j
│   │   ├── qdrant.py                  # Qdrant client setup for local Qdrant
│   │   ├── redis.py                   # Redis client setup for local Redis server
│   │   └── history.py                 # save_story(), save_qa(), get_stories(), get_qa()
│   ├── schemas/                        # Pydantic models for API + structured output
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   └── components/
│   │       ├── UploadPanel.jsx        # File upload + ingestion progress
│   │       ├── GraphVisualization.jsx # react-force-graph-2d rendering
│   │       ├── QueryInterface.jsx     # Question input + answer display
│   │       ├── CitationPanel.jsx      # Cited chunks and graph nodes
│   │       ├── HistorySidebar.jsx     # Past stories list
│   │       └── QAHistory.jsx          # Past Q&A for current story
│   ├── package.json
│   └── vite.config.js
├── docker-compose.yml
└── README.md
```

---

## 10. Environment Variables

```env
OPENAI_API_KEY=
# Docker Compose local setup (default)
NEO4J_URL=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASS=password
QDRANT_URL=http://qdrant:6333
REDIS_URL=redis://redis:6379
MONGODB_URL=mongodb://mongo:27017
MONGODB_DB=story_graphrag
```

If the backend is run outside Docker on the host machine, replace the service names above with `localhost` equivalents.

---

## 11. Docker Compose

```yaml
version: "3.9"
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - neo4j
      - qdrant
      - redis
      - mongo

  frontend:
    build: ./frontend
    ports:
      - "5173:5173"
    depends_on:
      - backend

  mongo:
    image: mongo:7
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db

  neo4j:
    image: neo4j:5
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      NEO4J_AUTH: neo4j/password
    volumes:
      - neo4j_data:/data

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  neo4j_data:
  qdrant_data:
  redis_data:
  mongo_data:
```
