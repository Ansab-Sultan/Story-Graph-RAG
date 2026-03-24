# Implementation Plan v1
## Story GraphRAG — Intelligent Story & Novel Analysis Engine

**Version:** 1.0  
**Author:** Muhammad Ansab Sultan  
**Date:** March 2026  
**Status:** Draft

---

## Overview

The build is split into 6 sequential phases. Each phase must work end-to-end before moving to the next. There are two separate LangGraph graphs in this project — the **Ingestion Pipeline** and the **Query Agent** — and they are built in separate phases so complexity never compounds.

---

## Phase 1 — Ingestion Pipeline (LangGraph)
**Goal:** Build the full document processing pipeline that takes a raw story file and produces a populated Neo4j graph + Qdrant vector index.

### Tasks

| # | Task | Notes |
|---|---|---|
| 1.1 | Set up Python environment | Python 3.11+, install `langgraph`, `langchain-openai`, `langchain-experimental`, `langchain-community`, `neo4j`, `qdrant-client`, `pypdf`, `pydantic`, `tiktoken` |
| 1.2 | Define `IngestionState` TypedDict | Fields: `story_id`, `title`, `raw_text`, `chunks`, `graph_docs`, `alias_map`, `graph_built`, `vectors_stored`, `progress` |
| 1.3 | Implement `loader.py` | Extract raw text from `.pdf` (pypdf) and `.txt`; use `RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=100)`; wrap each chunk as a LangChain `Document` with `story_id`, `chunk_id`, `chunk_index` metadata — no LLM involved |
| 1.4 | Implement `graph_extractor.py` | Initialize `LLMGraphTransformer` with `allowed_nodes`, `allowed_relationships`, `node_properties=["description"]`, `relationship_properties=["description"]`; call `await transformer.aconvert_to_graph_documents(state["chunks"])` — single async batched call that returns both nodes and relationships together |
| 1.5 | Implement `gleaning.py` | Initialize a second `LLMGraphTransformer` with `additional_instructions` asking for missed entities/relationships; run `aconvert_to_graph_documents` on the same chunks; merge new nodes and relationships into existing `graph_docs` |
| 1.6 | Implement `deduplication.py` | Collect all unique node names from `graph_docs`; make single LLM call using `llm.with_structured_output(DeduplicationOutput)` to group aliases; build `alias_map`; apply map to every `node.id`, `rel.source.id`, `rel.target.id` in `graph_docs` before Neo4j write |
| 1.7 | Implement `graph_builder.py` | Connect to Neo4j async driver; `MERGE` nodes and relationships using canonical names from deduplicated `graph_docs`; scope all writes to `story_id`; create indexes on `name` and `type`; **no embeddings** — Neo4j stores graph structure only |
| 1.8 | Implement `vector_embedder.py` | Batch embed `chunk.page_content` for all chunks using `text-embedding-3-small`; create Qdrant collection `story_{story_id}`; upsert all points — **this is the only place embeddings are created in the entire ingestion pipeline** |
| 1.9 | Wire ingestion graph in `ingestion/graph.py` | Nodes: `loader → graph_extractor → gleaning → deduplication → graph_builder` and `deduplication → vector_embedder`; graph_builder and vector_embedder run in parallel after deduplication |
| 1.10 | Test with a short story (~20 pages) | Run the ingestion graph directly; verify Neo4j browser at `localhost:7474` shows populated graph with correct node types and relationships; verify Qdrant collection has correct chunk count |
| 1.11 | Validate extraction and deduplication quality | Check that "Holmes", "Sherlock", "Mr. Holmes" collapse into one node; check relationship types are from the allowed list; tune `additional_instructions` in gleaning if important entities are missed |

### Exit Criteria
- Running the ingestion graph on a short story produces a populated graph in the Neo4j browser
- Qdrant collection for the story has the correct number of chunks
- Alias deduplication works — same character does not appear as multiple separate nodes
- Relationships are directional, typed correctly, and scoped to `story_id`
- Neo4j write uses zero embedding calls — confirmed by checking OpenAI API usage logs

---

## Phase 2 — Query Agent (LangGraph)
**Goal:** Build the query routing agent that classifies questions, generates Cypher queries, retrieves from the right source(s), and synthesizes a cited answer.  

### Tasks

| # | Task | Notes |
|---|---|---|
| 2.1 | Define `QueryState` TypedDict | Include: `story_id`, `question`, `query_type`, `cypher_query`, `graph_results`, `vector_results`, `answer`, `citations` |
| 2.2 | Implement `router.py` | Use `llm.with_structured_output(RouterOutput)` to classify question as `vector`, `graph`, or `hybrid`; test with at least 10 different question types to validate routing accuracy |
| 2.3 | Implement `cypher_generator.py` | Use `llm.with_structured_output(CypherOutput)` to convert natural language question to valid Cypher; always scope to `story_id`; include available node/relationship types in the prompt |
| 2.4 | Implement `graph_retriever.py` | Execute the generated Cypher against Neo4j async driver; return matched nodes and edges as structured dicts; handle empty results gracefully |
| 2.5 | Implement `vector_retriever.py` | Embed question with `text-embedding-3-small`; search Qdrant `story_{story_id}` collection for top 4 chunks; return chunks with metadata |
| 2.6 | Implement `answer_synthesizer.py` | Use `llm.with_structured_output(AnswerOutput)` to produce typed answer + citations; citations reference either `chunk_id` or `node_name + relationship_type` depending on source |
| 2.7 | Wire query graph in `query/graph.py` | Add all nodes; add conditional edge from router; add conditional edge from graph_retriever (goes to vector_retriever if hybrid, else answer_synthesizer) |
| 2.8 | Test all three routing paths | Write test questions for each path: pure vector, pure graph (1-hop), graph (2-hop), hybrid; verify correct routing and answer quality for each |
| 2.9 | Test Cypher generation quality | Run 5–10 graph questions and inspect generated Cypher in Neo4j browser; refine the Cypher generator prompt until queries are correct and scoped |

### Exit Criteria
- Router correctly classifies all 3 question types (validate with 10+ test questions)
- Graph questions produce valid Cypher that returns correct Neo4j results
- 2-hop queries work (e.g. enemies of allies)
- Hybrid questions retrieve from both sources and synthesize a combined answer
- Every answer includes at least one citation

---

## Phase 3 — FastAPI Backend
**Goal:** Wrap both LangGraph graphs in async FastAPI endpoints with SSE streaming for ingestion progress.  

### Tasks

| # | Task | Notes |
|---|---|---|
| 3.1 | Set up FastAPI project structure | `main.py`, `api/routes.py`, wire to ingestion and query graph modules |
| 3.2 | Implement `POST /api/stories` as `async` | Accept exactly one `.pdf` or `.txt` upload; reject the request if another ingestion job is already running; reject duplicate file names; save to `/tmp`; write `status: queued` to Redis; register `run_ingestion` as `BackgroundTasks.add_task()` — do NOT await; return `story_id` instantly |
| 3.3 | Implement `run_ingestion` as `async` background function | Set Redis status to `running`; hold a global ingestion lock so only one story is processed at a time; call `ingestion_graph.astream(stream_mode="updates")`; push each node completion event to Redis List `stream:{story_id}`; call `save_story()` and set status to `complete` when done; release the lock on completion/failure |
| 3.4 | Implement `GET /api/stories/{story_id}/stream` as `async` | SSE endpoint using `StreamingResponse`; cursor-based polling of Redis List; emits `progress` events per node; emits `complete` when status is complete |
| 3.5 | Implement `POST /api/stories/{story_id}/query` as `async` | Invoke `query_graph.ainvoke()` for the selected story; call `save_qa()` after response; return answer + citations |
| 3.6 | Implement `GET /api/stories/{story_id}/graph` as `async` | Query Neo4j for all nodes and edges for the story; return as `{nodes: [...], edges: [...]}` — used by the frontend graph visualization |
| 3.7 | Implement history endpoints as `async` | `GET /api/stories` (list for document-name selector), `GET /api/stories/{id}` (detail), `GET /api/stories/{id}/qa` (Q&A history) — all read from MongoDB and include stored file names |
| 3.8 | Add CORS middleware | Allow localhost:5173 during development |
| 3.9 | Test all endpoints with Postman | Verify `POST /stories` rejects concurrent ingestions and duplicate names; verify SSE streams one event per ingestion node; verify query endpoint returns answer + citations for the selected named document |

### Exit Criteria
- `POST /api/stories` returns `story_id` in under 200ms regardless of file size
- A second upload request is rejected while any ingestion job is running
- Stored documents are discoverable and selectable by file name
- SSE stream correctly reflects all 6 ingestion node completions in order (loader, graph_extractor, gleaning, deduplication, graph_builder, vector_embedder)
- Query endpoint returns correct answers with citations for all 3 query types
- `GET /api/stories/{story_id}/graph` returns all nodes and edges from Neo4j

---

## Phase 4 — React Frontend
**Goal:** Build a clean, visually impressive UI with file upload, graph visualization, and Q&A interface.  

### Tasks

| # | Task | Notes |
|---|---|---|
| 4.1 | Scaffold React + Vite project | Add TailwindCSS, `react-force-graph-2d`, `react-markdown` |
| 4.2 | Build `UploadPanel` component | Drag-and-drop or click-to-upload for one `.pdf`/`.txt`; calls `POST /api/stories`; disables upload while an ingestion is active; shows live ingestion progress from SSE stream with node-by-node status indicators |
| 4.3 | Build `GraphVisualization` component | Calls `GET /api/stories/{id}/graph` after ingestion; renders force-directed graph using `react-force-graph-2d`; color nodes by entity type; show tooltip on hover; highlight connected nodes on click |
| 4.4 | Build `QueryInterface` component | Requires the user to choose a stored PDF/TXT by name first, then sends questions to `POST /api/stories/{id}/query`; shows answer as formatted markdown; shows loading state while waiting |
| 4.5 | Build `CitationPanel` component | Renders below each answer; shows cited graph nodes/edges or text chunk excerpts; clearly distinguishes between graph citations and vector citations |
| 4.6 | Build `HistorySidebar` component | Calls `GET /api/stories` on mount; lists past stories by stored file name + date; clicking a name loads that story into the main view |
| 4.7 | Build `QAHistory` component | Calls `GET /api/stories/{id}/qa` when a story is loaded from history; displays all past Q&A pairs with their citations |
| 4.8 | Wire all components in `App.jsx` | Three-panel layout: sidebar (history) + main area (graph + query) + citation panel |
| 4.9 | Polish and responsive layout | App should look clean enough for a demo GIF; graph visualization is the hero element |

### Exit Criteria
- Uploading a story shows live progress and a populated graph when done
- Only one upload can be started at a time
- Graph nodes are colored by type and hoverable
- Stored stories are selectable by name before querying
- Asking a question returns a cited answer under 10 seconds
- Graph citations (node/edge) and text citations (chunk) look visually distinct
- History sidebar works — past stories are loadable with their Q&A

---

## Phase 5 — Dockerization
**Goal:** Package all 6 services so the project runs with one command.  

### Tasks

| # | Task | Notes |
|---|---|---|
| 5.1 | Write `backend/Dockerfile` | Python 3.11 slim, install requirements, run uvicorn |
| 5.2 | Write `frontend/Dockerfile` | Node 20 alpine, build Vite app, serve with nginx |
| 5.3 | Write `docker-compose.yml` | Wire all 6 local services: backend, frontend, local Neo4j, local Qdrant, local Redis, and local MongoDB; named volumes for all 4 data services |
| 5.4 | Add `.env.example` | Include local connection settings for Docker Compose (`neo4j`, `qdrant`, `redis`, `mongo`) and note the `localhost` equivalents for host-based runs |
| 5.5 | Test `docker compose up` from scratch | Pull images, start all local services, verify startup order and health |
| 5.6 | Add `.dockerignore` files | Exclude `node_modules`, `__pycache__`, `.env`, `/tmp` from builds |

### Exit Criteria
- `cp .env.example .env` → fill in OpenAI key → `docker compose up` → full app running entirely on the local machine
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
| 6.9 | Add repo topics | `graphrag`, `neo4j`, `langgraph`, `rag`, `knowledge-graph`, `fastapi`, `react`, `openai` |

### Exit Criteria
- README explains the GraphRAG vs RAG difference clearly to a non-technical reader
- Demo GIF shows a multi-hop graph question with the relationship path visually highlighted
- Repo is public and tagged

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Duplicate file names create ambiguous story selection | Medium | Medium | Enforce unique file names at upload time or require rename before ingestion; always show stored file name in the selector |
| `LLMGraphTransformer` extraction quality is poor on complex narratives | High | High | Spend extra time on Phase 1 prompt tuning (Task 1.11); tune `additional_instructions` on both the main transformer and the gleaning pass |
| Deduplication LLM misses aliases or over-merges distinct characters | Medium | High | Validate the `alias_map` output manually on a test story before applying; add a human-review log of what was merged |
| Gleaning pass adds noise instead of new signal | Low | Medium | Compare node counts before and after gleaning; if no new meaningful nodes are added, the gleaning prompt needs refinement |
| Cypher generator produces invalid or unscoped queries | Medium | High | Include full schema in every Cypher prompt; wrap Neo4j execution in try/except; fall back to vector search if Cypher fails |
| Router misclassifies question type | Medium | Medium | Test router with 20+ diverse questions in Phase 2; add few-shot examples to the router prompt if accuracy is low |
| Neo4j Cypher scoping bug leaks data across stories | Low | High | Every Cypher query must filter by `story_id` — enforce in the Cypher generator prompt and add a validation step before execution |
| Large novels (300+ pages) make gleaning + deduplication slow | Medium | Medium | Cap gleaning to one pass only; batch deduplication name list to avoid hitting context limits |
| react-force-graph-2d performance degrades on large graphs | Medium | Low | Limit initial render to CHARACTER and PLACE nodes; let user toggle other entity types |
| OpenAI API costs spike during ingestion of large files | Medium | Low | Use `gpt-4o-mini` for all LLM calls; embeddings via `text-embedding-3-small` are cheap; estimate cost per page before ingestion |

---

## Dependencies & Services Required

| Service | Purpose | Free Tier |
|---|---|---|
| OpenAI API | LLM for extraction + answering + embeddings | Pay-per-use, ~$0.05–0.20 per story ingestion depending on size |
| Neo4j | Local graph database for entity/relationship storage and Cypher traversal | Free self-hosted via Docker |
| Qdrant | Local vector store for chunk similarity search | Free self-hosted via Docker |
| MongoDB | Local history store for stories + Q&A sessions | Free self-hosted via Docker |
| Redis | Local job state bridge for SSE streaming | Free self-hosted via Docker |

---

## Definition of Done

The project is complete when:
- [ ] All 6 phases pass their exit criteria
- [ ] A multi-hop graph question (2+ hops) returns a correct, cited answer
- [ ] `docker compose up` runs with zero manual steps beyond API keys
- [ ] Interactive graph visualization renders and is interactive
- [ ] Demo GIF recorded and embedded in README
- [ ] Repo is public on GitHub with appropriate topics
