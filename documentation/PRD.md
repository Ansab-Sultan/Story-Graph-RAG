# Product Requirements Document (PRD)
## Story GraphRAG — Intelligent Story & Novel Analysis Engine

**Version:** 1.0  
**Author:** Muhammad Ansab Sultan  
**Date:** March 2026  
**Status:** Draft

---

## 1. Overview

### 1.1 Product Summary
Story GraphRAG is a full-stack AI application that allows users to upload any story, novel, or narrative document and ask deep, relationship-aware questions about it. Unlike traditional RAG systems that retrieve text by similarity, Story GraphRAG builds a knowledge graph of characters, events, places, and relationships from the story. Graph data is stored in local Neo4j, chunk embeddings are stored in local Qdrant, story metadata plus story-scoped chat metadata are stored in local MongoDB, and LangGraph conversation memory is persisted in MongoDB through the MongoDB checkpointer. Ingestion progress is coordinated through a local Redis server. The backend uses a Gemini chat model for extraction and answer generation, and a local BAAI embedding model for vector search, enabling multi-hop reasoning that flat vector search fundamentally cannot do.

### 1.2 Motivation
Standard RAG works well for factual lookup but breaks down when a question requires reasoning across relationships — "Who are the enemies of Harry's allies?" or "Which characters indirectly caused the final battle?" are questions no similarity search can answer reliably. Graphs can. Stories are the perfect domain to demonstrate this gap publicly because everyone understands narratives, making the demo universally relatable.

### 1.3 Goals
- Build and showcase a production-grade GraphRAG system publicly on GitHub
- Demonstrate the clear advantage of graph-based retrieval over flat vector search through a compelling, visual demo
- Establish a distinct, creative project that complements the Deep Research Agent in the portfolio

---

## 2. Target Users

| User Type | Description |
|---|---|
| Book Enthusiasts & Readers | Want to explore and query complex narratives they've read |
| Writers & Authors | Want to analyze character relationships and plot consistency in their own work |
| Students & Educators | Studying literature and want structured analysis of texts |
| AI/ML Developers | Want to learn from or contribute to a real GraphRAG implementation |
| Recruiters & Hiring Managers | Evaluating the depth of an AI engineer's graph + RAG capabilities |

---

## 3. User Stories

- **As a user**, I want to upload one story or novel at a time as a `.pdf` or `.txt` so that each ingestion run is isolated and predictable.
- **As a user**, I want to ask relationship-aware questions like "Who are the enemies of the protagonist's allies?" so that I get answers that require reasoning across multiple characters and events.
- **As a user**, I want to see a visual graph of characters and their relationships so that I can understand the story's structure at a glance.
- **As a user**, I want the system to cite which characters, events, or text passages it used to answer my question so that I can verify the answer.
- **As a user**, I want to ask simple factual questions and still get fast, accurate answers so that the system works for both simple and complex queries.
- **As a user**, I want to select the exact stored PDF or TXT by its name before asking a question so that answers come from the document I chose.
- **As a user**, I want each stored story to support multiple independent chats so that I can explore different lines of questioning without mixing context.
- **As a user**, I want follow-up questions inside the same chat to remember earlier turns so that the experience feels like a real chatbot instead of isolated one-off queries.
- **As a user**, I want to see why the system chose graph, vector, or hybrid retrieval and what evidence it actually used so that I can trust and inspect the answer.
- **As a developer**, I want clean API endpoints so that I can integrate the story analysis engine into other tools.

---

## 4. Features

### 4.1 Core Features (MVP)

| # | Feature | Description | Priority |
|---|---|---|---|
| F1 | Story Upload | Upload exactly one story or novel at a time as a `.pdf` or `.txt` file; ingestion does not accept multiple files in a single run | P0 |
| F2 | Entity & Relationship Extraction | Story is chunked using `RecursiveCharacterTextSplitter`, then `LLMGraphTransformer` extracts nodes and relationships. A contextual gleaning pass is shown the first-pass extraction for the same chunk and asked for only genuinely new entities/relationships. A deduplication pass collapses aliases into canonical names, and the backend enforces code-level node/relationship deduplication before writing the graph to local Neo4j and chunk embeddings to local Qdrant | P0 |
| F3 | Hybrid Retrieval Agent | Agentic query router that decides whether to use vector search from local Qdrant, graph traversal from local Neo4j, or both based on the question type, and stores a short routing reason explaining why that path was chosen | P0 |
| F4 | Cited Answers + Retrieval Evidence | Every answer cites the specific characters, events, relationships, or text chunks it used, and the full retrieval evidence is persisted with each assistant chat message for frontend inspection later | P0 |
| F5 | Ingestion Progress Streaming | Real-time progress updates shown to the user during the extraction and graph building phase, coordinated through the local Redis server | P0 |
| F6 | Named Story Selection | Each stored PDF or TXT is saved and surfaced by its file name, and the user must select that named document before asking questions | P0 |
| F7 | Story-Scoped Multi-Chat Memory | Every `story_id` can have multiple chats, each chat has its own `chat_id`, and the query agent remembers prior turns inside that chat using LangGraph MongoDB checkpoint persistence | P0 |

### 4.2 Enhanced Features (Post-MVP)

| # | Feature | Description | Priority |
|---|---|---|---|
| F8 | Interactive Graph Visualization | Visual, interactive graph explorer of all characters and relationships rendered in the frontend using `@react-sigma/core` + Graphology, with WebGL rendering and ForceAtlas2 layout for a professional knowledge-graph experience | P1 |
| F9 | Multi-Story Library | Persist multiple previously ingested stories and let the user switch between them by document name; each gets its own isolated Neo4j subgraph, Qdrant collection, chat set, and MongoDB history record | P1 |
| F10 | Chat History & Resume | Each story exposes its past chats so users can reopen an old conversation, continue it with preserved context, and inspect routing reasons plus retrieval evidence for every assistant turn | P1 |
| F11 | Chunk Browser | Frontend can request and display all stored chunks for a selected story so users can inspect the chunk corpus alongside the graph | P1 |
| F12 | Relationship Deep Dive | Click any character or relationship in the graph to get a detailed AI-generated summary of that entity | P2 |
| F13 | Conflict & Theme Detection | Agent automatically identifies and surfaces major conflicts, themes, and character arcs without the user asking | P2 |

---

## 5. Query Types the System Must Handle

This is the core product requirement that defines the retrieval architecture:

| Query Type | Example | Retrieval Method |
|---|---|---|
| Simple factual | "Where does the story take place?" | Local Qdrant vector search |
| Character lookup | "Describe Sherlock Holmes" | Local Qdrant vector search |
| Direct relationship | "Who is Watson's friend?" | Local Neo4j traversal — 1 hop |
| Multi-hop relationship | "Who are the enemies of Holmes's allies?" | Local Neo4j traversal — 2+ hops |
| Event-causal | "Which events led to the final confrontation?" | Local Neo4j causal-chain traversal |
| Cross-entity | "Which characters were present at events caused by Moriarty?" | Local Neo4j + local Qdrant hybrid |
| Thematic | "What does the story say about loyalty?" | Local Qdrant vector search |

---

## 6. User Flow

```
User uploads one story (.pdf or .txt)
        ↓
System processes the file:
  [✓ Chunking document...]
  [✓ Extracting entities & relationships — chunk 4/20...]
  [✓ Writing graph entities and relationships to local Neo4j...]
  [✓ Writing chunk embeddings to local Qdrant...]
  [✓ Saving story metadata to local MongoDB...]
  [✓ Story ready!]
        ↓
Stored story is listed in the library by file name
        ↓
User selects the desired PDF/TXT by name
        ↓
Frontend loads available chats for that `story_id`
        ↓
User opens an existing chat or sends the first message without a `chat_id`
        ↓
If no `chat_id` was sent, backend creates a new `chat_id` and uses it as the LangGraph `thread_id`
        ↓
User sees interactive graph visualization (characters, places, events)
        ↓
User types a question
        ↓
Agent routes the question:
  → Simple: Qdrant retrieval → Answer with text citations
  → Relational: Neo4j traversal → Answer with relationship citations
  → Complex: Both → Merged answer with combined citations
        ↓
Answer displayed with cited sources (chunks and/or graph nodes/edges), routing reason, and persisted retrieval evidence
        ↓
Assistant turn is persisted to the story-scoped chat transcript, and future turns in the same chat reuse the saved LangGraph memory
```

---

## 7. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Ingestion time | < 3 minutes for a 300-page novel |
| Query response time | < 10 seconds for any question type |
| Graph traversal depth | Up to 4 hops |
| Max story size | 500 pages / ~250,000 words |
| Concurrent ingestion jobs | 1 active upload/ingestion job at a time |
| Uptime | 99.9% (Docker-based, restartable) |

---

## 8. Out of Scope (v1)

- User authentication and accounts
- Real-time collaborative annotation
- Audio or video story formats
- Fine-tuned models for entity extraction
- Mobile native app

---

## 9. Success Metrics

- GitHub stars and forks (community adoption)
- Ratio of multi-hop questions answered correctly vs flat RAG baseline
- Ingestion time per page
- Graph density (average relationships per character) as a quality indicator
- Demo GIF engagement (click-through from README)
