# Story Graph RAG

![Python](https://img.shields.io/badge/Python-3.11%2B-blue) ![Next.js](https://img.shields.io/badge/Next.js-15%2B-black) ![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-green) ![Neo4j](https://img.shields.io/badge/Neo4j-GraphDB-lightgrey) ![Qdrant](https://img.shields.io/badge/Qdrant-VectorDB-red)

Story Graph RAG is an intelligent application that leverages Graph-based Retrieval Augmented Generation to extract, structure, and explore narratives. It transforms unstructured story data into interactive knowledge graphs and offers contextual, graph-powered question answering.

## Key Features

*   **Knowledge Graph Extraction:** Dynamically parse unstructured text to infer and build relationships.
*   **Graph RAG Pipeline:** Context-aware query routing relying on graph queries (via Neo4j) and vector search (via Qdrant).
*   **Interactive Visualization:** A rich, responsive React/Sigma.js-driven UI for exploring nodes, edges, and story arcs.
*   **Agentic Q&A:** Employs LangGraph to intelligently route agentic questions for precise, context-rich answers.

---

## 🚀 Quick Start

### Prerequisites
Before you begin, ensure you have the following installed:
*   **Python 3.11+**
*   **Node.js 18+**
*   **Docker & Docker Compose** (for database containers)
*   **`uv`** (Python package installer)
*   **Redis** (for background tasks/caching)
*   **MongoDB** (for document storage and checkpoints)

### Installation

**1. Clone & Env Setup**
```bash
git clone https://github.com/Ansab-Sultan/Story-Graph-RAG.git
cd Story-Graph-RAG

# Set up environment variables
cp backend/.env.example backend/.env
```
> **Note:** Open `backend/.env` and configure your necessary API keys (e.g., `GOOGLE_API_KEY`).

**2. Infrastructure Startup (Docker)**
The project relies on localized Docker configurations for stateful databases. You must spin up both Neo4j and Qdrant:
```bash
# Start Neo4j (Graph Database)
cd backend/neo4j
docker compose up -d

# Start Qdrant (Vector Database)
cd ../qdrant
docker compose up -d
cd ../../
```

**3. Local System Services (Redis & MongoDB)**
You must have a Redis server running locally on your system.
*   **Ubuntu / Debian:**
    ```bash
    sudo apt update
    sudo apt install redis-server
    sudo systemctl enable --now redis-server
    ```
*   **macOS (Homebrew):**
    ```bash
    brew install redis
    brew services start redis
    ```
*(You will also need MongoDB running locally on its default port `27017` to satisfy the `.env.example` defaults).*

**4. Backend Startup (via `uv`)**
This project relies on the extremely fast `uv` package manager for Python dependencies. This ensures tight consistency.
```bash
cd backend

# Sync dependencies exactly as specified in uv.lock
uv sync

# Start the FastAPI server
uv run uvicorn app.main:app --reload
```

**5. Frontend Startup**
In a new terminal window, start the Next.js React frontend:
```bash
cd frontend
npm install
npm run dev
```

---

## Usage
Once both servers and all infrastructure components are successfully running:
*   **Web Application:** Open your browser to `http://localhost:3000` to interact with the story graph.
*   **API Documentation:** Navigate to `http://localhost:8000/docs` to view the interactive Swagger/OpenAPI specifications.

---

## 📚 Documentation
> *For detailed Architecture, Business Logic, and API Reference, please see the [Documentation Folder](./documentation).*
