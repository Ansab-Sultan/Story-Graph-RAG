# Implementation Plan v1
## Story GraphRAG — Intelligent Story & Novel Analysis Engine

**Version:** 1.0  
**Author:** Muhammad Ansab Sultan  
**Date:** March 2026  
**Status:** Draft

---

## Overview

The build is split into 6 sequential phases. Each phase must work end-to-end before moving to the next. There are two separate LangGraph graphs in this project, the **Ingestion Pipeline** and the **Query Agent**, and they are built in separate phases so complexity never compounds. Query-side conversational memory is story-scoped: each `story_id` can own multiple chats, and each `chat_id` is also the LangGraph `thread_id`.

---

## Phase 1 — Ingestion Pipeline (LangGraph)
**Goal:** Build the full document processing pipeline that takes a raw story file and produces a populated Neo4j graph + Qdrant vector index.

### Tasks

| # | Task | Notes |
|---|---|---|
| 1.1 | Set up Python environment | Python 3.12+, install `langgraph`, `langchain-google-genai`, `langchain-experimental`, `langchain-community`, `sentence-transformers`, `neo4j`, `qdrant-client`, `pypdf`, and `pydantic-settings` |
| 1.2 | Define `IngestionState` TypedDict | Fields: `story_id`, `title`, `raw_text`, `graph_chunks`, `vector_chunks`, `graph_docs`, `alias_map`, `graph_built`, `vectors_stored`, `progress` |
| 1.3 | Implement `loader.py` | Extract raw text from `.pdf` (pypdf) and `.txt`; build two chunk streams from the same raw text using `RecursiveCharacterTextSplitter`: graph chunks (`GRAPH_CHUNK_SIZE=9000`, `GRAPH_CHUNK_OVERLAP=1000`) and vector chunks (`VECTOR_CHUNK_SIZE=600`, `VECTOR_CHUNK_OVERLAP=100`); wrap each chunk as a LangChain `Document` with `story_id`, `chunk_id`, `chunk_index`, and `chunk_kind` metadata — no LLM involved |
| 1.4 | Implement `graph_extractor.py` | Initialize `LLMGraphTransformer` with `allowed_nodes`, `allowed_relationships`, `node_properties=["description"]`, `relationship_properties=["description"]`; call `await transformer.aconvert_to_graph_documents(state["graph_chunks"])` so the extractor sees the larger context windows |
| 1.5 | Implement `gleaning.py` | Build a contextual second-pass `LLMGraphTransformer` per graph chunk, include the already extracted nodes/relationships from that exact graph chunk in the prompt, ask for only genuinely new entities/relationships, and merge with code-level node/edge deduplication |
| 1.6 | Implement `deduplication.py` | Collect all unique node names from `graph_docs`; make single LLM call using `llm.with_structured_output(DeduplicationOutput)` to group aliases; build `alias_map`; apply map to every `node.id`, `rel.source.id`, `rel.target.id` in `graph_docs`; then run a second code-level graph dedup pass so alias collapse cannot create duplicate edges |
| 1.7 | Implement `graph_builder.py` | Connect to Neo4j async driver; `MERGE` nodes and relationships using canonical names from deduplicated `graph_docs`; scope all writes to `story_id`; create indexes on `name` and `type`; **no embeddings** — Neo4j stores graph structure only |
| 1.8 | Implement `vector_embedder.py` | Batch embed `chunk.page_content` for all `vector_chunks` using `BAAI/bge-small-en-v1.5`; infer vector size dynamically before creating Qdrant collection `story_{story_id}`; upsert all points — **this is the only place document embeddings are created in the ingestion pipeline** |
| 1.9 | Wire ingestion graph in `ingestion/graph.py` | Nodes: `loader → graph_extractor → gleaning → deduplication → graph_builder` and `deduplication → vector_embedder`; graph_builder and vector_embedder run in parallel after deduplication |
| 1.10 | Test with a short story (~20 pages) | Run the ingestion graph directly; verify Neo4j browser at `localhost:7474` shows populated graph with correct node types and relationships; verify Qdrant collection has correct chunk count |
| 1.11 | Validate extraction and deduplication quality | Check that "Holmes", "Sherlock", "Mr. Holmes" collapse into one node; check relationship types are from the allowed list; verify contextual gleaning only adds genuinely new items and does not duplicate relationships |

### Exit Criteria
- Running the ingestion graph on a short story produces a populated graph in the Neo4j browser
- Qdrant collection for the story has the correct number of vector chunks
- Alias deduplication works — same character does not appear as multiple separate nodes
- Relationships are directional, typed correctly, and scoped to `story_id`
- Neo4j write uses zero embedding calls — all vector creation is isolated to the Qdrant embedding step

---

## Phase 2 — Query Agent (LangGraph)
**Goal:** Build the query routing agent that classifies questions, generates Cypher queries, retrieves from the right source(s), and synthesizes a cited answer.  

### Tasks

| # | Task | Notes |
|---|---|---|
| 2.1 | Define `QueryState` TypedDict | Include: `story_id`, `question`, `messages`, `transcript`, `query_type`, `routing_reason`, `cypher_query`, `graph_results`, `vector_results`, `evidence`, `answer`, `citations` |
| 2.2 | Implement `router.py` | Use `llm.with_structured_output(RouterOutput)` to classify question as `vector`, `graph`, or `hybrid`; persist the one-line `routing_reason`; pass recent chat history into the router prompt so follow-up turns can be routed correctly |
| 2.3 | Implement `cypher_generator.py` | Use `llm.with_structured_output(CypherOutput)` to convert natural language question to valid Cypher; always scope to `story_id`; include available node/relationship types in the prompt and recent message history for follow-up resolution |
| 2.4 | Implement `graph_retriever.py` | Execute the generated Cypher against Neo4j async driver; return matched nodes and edges as structured dicts; handle empty results gracefully |
| 2.5 | Implement `vector_retriever.py` | Build a contextualized search query from recent transcript history plus the current user message; embed with `BAAI/bge-small-en-v1.5`; search Qdrant `story_{story_id}` collection for top 4 chunks; return chunks with metadata |
| 2.6 | Implement `answer_synthesizer.py` | Use `llm.with_structured_output(AnswerOutput)` to produce typed answer + citations; citations reference either `chunk_id` or `node_name + relationship_type` depending on source; append assistant message and structured transcript item to state |
| 2.7 | Wire query graph in `query/graph.py` | Add all nodes; add conditional edge from router; add conditional edge from graph_retriever (goes to vector_retriever if hybrid, else answer_synthesizer) |
| 2.8 | Test all three routing paths | Write test questions for each path: pure vector, pure graph (1-hop), graph (2-hop), hybrid; verify correct routing and answer quality for each |
| 2.9 | Test Cypher generation quality | Run 5–10 graph questions and inspect generated Cypher in Neo4j browser; refine the Cypher generator prompt until queries are correct and scoped |
| 2.10 | Add LangGraph MongoDB checkpointer | Compile the query graph with `MongoDBSaver`; pass `config={"configurable": {"thread_id": chat_id}}` on every query so chat memory persists across turns and restarts |
| 2.11 | Persist retrieval evidence in transcript | Store `routing_reason` plus graph evidence (`nodes`, `relationships`, `raw_results`) and/or vector evidence (`chunk_ids`, `chunks`) with every assistant transcript message |

### Exit Criteria
- Router correctly classifies all 3 question types (validate with 10+ test questions)
- Graph questions produce valid Cypher that returns correct Neo4j results
- 2-hop queries work (e.g. enemies of allies)
- Hybrid questions retrieve from both sources and synthesize a combined answer
- Every answer includes at least one citation
- Same-chat follow-up questions work through LangGraph checkpointed memory
- Every persisted assistant transcript item includes `routing_reason` and source-specific retrieval evidence

---

## Phase 3 — FastAPI Backend
**Goal:** Wrap both LangGraph graphs in async FastAPI endpoints with SSE streaming for ingestion progress.  

### Tasks

| # | Task | Notes |
|---|---|---|
| 3.1 | Set up FastAPI project structure | `main.py` as the single app bootstrap, `create_index.py` for startup story/chat MongoDB indexes plus Neo4j indexes, and package layout under `app/` with `core`, `services`, `schemas`, `routers`, and `graph_rag_agent` |
| 3.2 | Implement `POST /api/stories` as `async` | Accept exactly one `.pdf` or `.txt` upload; reject the request if another ingestion job is already running; reject duplicate file names; save to `/tmp`; write `status: queued` to Redis; register `run_ingestion` as `BackgroundTasks.add_task()` — do NOT await; return `story_id` instantly |
| 3.3 | Implement `run_ingestion` as `async` background function | Set Redis status to `running`; hold a global ingestion lock so only one story is processed at a time; call `ingestion_graph.astream(stream_mode="updates")`; push each node completion event to Redis List `stream:{story_id}`; call `save_story()` and set status to `complete` when done; release the lock on completion/failure |
| 3.4 | Implement `GET /api/stories/{story_id}/stream` as `async` | SSE endpoint using `StreamingResponse`; cursor-based polling of Redis List; emits `progress` events per node; emits `complete` when status is complete |
| 3.5 | Implement `POST /api/stories/{story_id}/chats/messages` as `async` | If `chat_id` is omitted, create a new UUID4 chat and use it as LangGraph `thread_id`; otherwise verify the chat belongs to the story; invoke `query_graph.ainvoke()` with `configurable.thread_id`; return answer + citations + `routing_reason` + `evidence` |
| 3.6 | Implement `GET /api/stories/{story_id}/graph` as `async` | Query Neo4j for all nodes and edges for the story; return as `{nodes: [...], edges: [...]}` — used by the frontend graph visualization |
| 3.7 | Implement `GET /api/stories/{story_id}/chunks` as `async` | Read the full ordered chunk list for the story from Qdrant and return it for frontend evidence inspection |
| 3.8 | Implement story + chat history endpoints as `async` | `GET /api/stories` (list for document-name selector), `GET /api/stories/{id}` (detail), `GET /api/stories/{id}/chats` (chat list), `GET /api/stories/{id}/chats/{chat_id}` (chat summary), `GET /api/stories/{id}/chats/{chat_id}/messages` (transcript from LangGraph state) |
| 3.9 | Add CORS middleware | Allow `*` for the current frontend integration setup |
| 3.10 | Test all endpoints with Postman | Verify `POST /stories` rejects concurrent ingestions and duplicate names; verify SSE streams one event per ingestion node; verify sending a first chat message without `chat_id` creates a new chat and verify a second turn with the same `chat_id` uses preserved memory |

### Exit Criteria
- `POST /api/stories` returns `story_id` in under 200ms regardless of file size
- A second upload request is rejected while any ingestion job is running
- Stored documents are discoverable and selectable by file name
- SSE stream correctly reflects all 6 ingestion node completions in order (loader, graph_extractor, gleaning, deduplication, graph_builder, vector_embedder)
- Chat message endpoint returns correct answers with citations for all 3 query types
- A new chat can be created implicitly by omitting `chat_id`, and an existing chat can be resumed by reusing `chat_id`
- `GET /api/stories/{story_id}/graph` returns all nodes and edges from Neo4j
- `GET /api/stories/{story_id}/chunks` returns the ordered chunk list for the selected story

---

## Phase 4 — React Frontend
**Goal:** Build a clean, visually impressive UI with file upload, graph visualization, and story-scoped chat interface.  

### Tasks

| # | Task | Notes |
|---|---|---|
| 4.1 | Scaffold React + Vite project | Add TailwindCSS, `@react-sigma/core`, `graphology`, `@react-sigma/layout-forceatlas2`, and `react-markdown` |
| 4.2 | Build `UploadPanel` component | Drag-and-drop or click-to-upload for one `.pdf`/`.txt`; calls `POST /api/stories`; disables upload while an ingestion is active; shows live ingestion progress from SSE stream with node-by-node status indicators |
| 4.3 | Build `GraphVisualization` component | Calls `GET /api/stories/{id}/graph` after ingestion; loads the result into Graphology; renders the graph through Sigma.js with ForceAtlas2 layout; color nodes by entity type; show tooltip on hover; highlight connected nodes on click |
| 4.4 | Build `QueryInterface` component | Requires the user to choose a stored PDF/TXT by name first, then sends messages to `POST /api/stories/{id}/chats/messages`; if there is no active chat, omit `chat_id` so the backend creates one; shows answer as formatted markdown plus the returned `routing_reason`; shows loading state while waiting |
| 4.5 | Build `CitationPanel` component | Renders below each answer; shows cited graph nodes/edges or text chunk excerpts; clearly distinguishes between graph citations and vector citations; can expand into persisted retrieval evidence |
| 4.6 | Build `HistorySidebar` component | Calls `GET /api/stories` on mount; lists past stories by stored file name + date; clicking a name loads that story into the main view |
| 4.7 | Build `ChatSidebar` and `ChatTranscript` components | `ChatSidebar` calls `GET /api/stories/{id}/chats`; `ChatTranscript` calls `GET /api/stories/{id}/chats/{chat_id}/messages`; together they display all prior chat turns with citations, routing reasons, and evidence |
| 4.8 | Build `ChunkBrowser` component | Calls `GET /api/stories/{id}/chunks`; displays ordered chunks for the selected story so users can inspect the vector corpus directly |
| 4.9 | Wire all components in `App.jsx` | Three-panel layout: sidebar (history) + main area (graph + query) + evidence / citation panel |
| 4.10 | Polish and responsive layout | App should look clean enough for a demo GIF; graph visualization is the hero element |

### Exit Criteria
- Uploading a story shows live progress and a populated graph when done
- Only one upload can be started at a time
- Graph nodes are colored by type and hoverable
- Stored stories are selectable by name before querying
- Sending a chat message returns a cited answer under 10 seconds
- Graph citations (node/edge) and text citations (chunk) look visually distinct
- History sidebar works — past stories are loadable with their chats
- Query UI can show why the backend chose graph, vector, or hybrid retrieval
- Chunk browser works for the selected story

---

## Phase 5 — Local Infra & Environment
**Goal:** Standardize the local runtime so Neo4j and Qdrant run from dedicated Docker files, MongoDB and Redis run as local host services, and backend env defaults are explicit.  

### Tasks

| # | Task | Notes |
|---|---|---|
| 5.1 | Add `backend/neo4j/docker-compose.yml` | Run Neo4j locally with ports `7474` / `7687`, persistent storage, auth, and healthcheck |
| 5.2 | Keep `backend/qdrant/docker-compose.yml` | Run Qdrant locally with persistent storage and healthcheck |
| 5.3 | Add `.env.example` | Include `GOOGLE_API_KEY`, `GOOGLE_CHAT_MODEL`, `EMBEDDING_MODEL`, `EMBEDDING_DEVICE`, `EMBEDDING_NORMALIZE`, checkpoint collection names, chat UI limits, infrastructure timeout, and localhost connection settings for Neo4j, Qdrant, Redis, and MongoDB |
| 5.4 | Document local services | Redis and MongoDB are expected as host-installed services on `localhost`; Neo4j and Qdrant are started from their dedicated compose files |
| 5.5 | Test startup from scratch | Start Neo4j and Qdrant from their compose files; verify backend health endpoint sees all four data services |
| 5.6 | Verify startup index creation | Confirm `create_index.py` runs on backend startup and creates story/chat MongoDB indexes plus Neo4j indexes automatically; LangGraph checkpoint indexes are created by `MongoDBSaver` |

### Exit Criteria
- `cp .env.example .env` → fill in Google API key → start Neo4j and Qdrant from their compose files → backend runs against all local services
- Neo4j browser accessible at `localhost:7474`
- Qdrant accessible at `localhost:6333`, Redis at `localhost:6379`, MongoDB at `localhost:27017`
- All services healthy and interconnected

---

## Phase 6 — Polish & GitHub Release
**Goal:** Make the repo visually impressive, educational, and discoverable.  

### Tasks

| # | Task | Notes |
|---|---|---|
| 6.1 | Write `README.md` | Cover: what it is, the GraphRAG vs flat RAG comparison table, demo GIF, architecture diagram, quickstart, tech stack, example questions |
| 6.2 | Record demo GIF | Upload a well-known short story → show graph building live → ask a multi-hop question → show the graph highlight the cited path |
| 6.3 | Add architecture diagram to README | Show both LangGraph graphs (ingestion + query) and all 4 data services |
| 6.4 | Add "Why GraphRAG?" section to README | Short explanation with a concrete before/after example showing where flat RAG fails and GraphRAG succeeds — this is the hook |
| 6.5 | Write code comments on all nodes | Makes the codebase educational; future contributors and readers should understand each node's role |
| 6.6 | Add `CONTRIBUTING.md` | Guide for opening issues and PRs |
| 6.7 | Add GitHub Actions CI | Ruff lint for Python, ESLint for React, on every push |
| 6.8 | Tag `v1.0.0` release | GitHub release with release notes |
| 6.9 | Add repo topics | `graphrag`, `neo4j`, `langgraph`, `rag`, `knowledge-graph`, `fastapi`, `react`, `gemini` |

### Exit Criteria
- README explains the GraphRAG vs RAG difference clearly to a non-technical reader
- Demo GIF shows a multi-hop graph question with the relationship path visually highlighted
- Repo is public and tagged

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Duplicate file names create ambiguous story selection | Medium | Medium | Enforce unique file names at upload time or require rename before ingestion; always show stored file name in the selector |
| Chat is resumed under the wrong story | Low | High | Every chat lookup must validate both `story_id` and `chat_id`; never allow a `chat_id` from one story to be queried under another |
| `LLMGraphTransformer` extraction quality is poor on complex narratives | High | High | Spend extra time on Phase 1 prompt tuning (Task 1.11); tune `additional_instructions` on both the main transformer and the gleaning pass |
| Deduplication LLM misses aliases or over-merges distinct characters | Medium | High | Validate the `alias_map` output manually on a test story before applying; add a human-review log of what was merged |
| Gleaning pass adds noise instead of new signal | Low | Medium | Compare node counts before and after gleaning; if no new meaningful nodes are added, the gleaning prompt needs refinement |
| Cypher generator produces invalid or unscoped queries | Medium | High | Include full schema in every Cypher prompt; wrap Neo4j execution in try/except; fall back to vector search if Cypher fails |
| Router misclassifies question type | Medium | Medium | Test router with 20+ diverse questions in Phase 2; add few-shot examples to the router prompt if accuracy is low |
| Neo4j Cypher scoping bug leaks data across stories | Low | High | Every Cypher query must filter by `story_id` — enforce in the Cypher generator prompt and add a validation step before execution |
| Large graph chunks increase extraction and gleaning latency on long novels | Medium | Medium | Keep vector chunks small for retrieval, keep gleaning to one pass only, and tune graph chunk size / overlap if the selected LLM or hardware becomes the bottleneck |
| Sigma ForceAtlas2 layout becomes noisy on dense graphs | Medium | Low | Tune layout iterations and node sizing; provide filters or type toggles for large story graphs; retain Graphology data so the layout and render layer stay decoupled |
| Gemini API costs or quotas spike during ingestion of large files | Medium | Low | Keep Gemini model on the lightweight Flash-Lite tier; estimate cost per page before ingestion; embeddings remain local via BAAI |
| Local BGE embedding runtime is heavy on some machines | Medium | Medium | Default to CPU, document memory expectations, and make embedding device configurable via env |
| MongoDB checkpointer startup fails when local MongoDB is down | Medium | High | Fail fast in development, document the dependency clearly, and keep integration tests skip-aware when local infra is unavailable |

---

## Dependencies & Services Required

| Service | Purpose | Free Tier |
|---|---|---|
| Gemini API | LLM for extraction, routing, Cypher generation, and answering | Pay-per-use |
| BAAI `bge-small-en-v1.5` | Local embedding model for chunk and query vectors | Free local model |
| Neo4j | Local graph database for entity/relationship storage and Cypher traversal | Free self-hosted via Docker |
| Qdrant | Local vector store for chunk similarity search | Free self-hosted via Docker |
| MongoDB | Local store for stories, chat metadata, and LangGraph checkpoint persistence | Free local host service |
| Redis | Local job state bridge for SSE streaming | Free local host service |

---

## Definition of Done

The project is complete when:
- [ ] All 6 phases pass their exit criteria
- [ ] A multi-hop graph question (2+ hops) returns a correct, cited answer
- [ ] Neo4j and Qdrant start from their dedicated compose files and backend runs cleanly against local MongoDB + Redis
- [ ] Interactive graph visualization renders and is interactive
- [ ] A same-chat follow-up question works because prior memory is restored through the MongoDB checkpointer
- [ ] Demo GIF recorded and embedded in README
- [ ] Repo is public on GitHub with appropriate topics
