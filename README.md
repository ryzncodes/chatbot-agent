# ZUS AI Assistant

An end-to-end conversational agent that plans, calls external tools, and retrieves domain knowledge for ZUS Coffee. This README covers setup, architecture, testing, and deployment guidance for local development and production rollouts. For detailed product requirements, see [`prd.md`](prd.md).

## Table of Contents

1. [Features](#features)
2. [Repository Layout](#repository-layout)
3. [Prerequisites](#prerequisites)
4. [Environment Variables](#environment-variables)
5. [Setup & Run Instructions](#setup--run-instructions)
6. [Architecture Overview](#architecture-overview)
7. [Key Trade-Offs](#key-trade-offs)
8. [Testing Strategy](#testing-strategy)
9. [Deployment Notes](#deployment-notes)
10. [Documentation Bundle](#documentation-bundle)

## Features

- Multi-turn memory with slot tracking across threads.
- Planner/controller loop that selects between calculator, RAG, Text2SQL, or fallback actions.
- FastAPI backend exposing `/chat` and `/metrics`, with tool routes under `/tools` (`/tools/calculator`, `/tools/products`, `/tools/outlets`) and top-level aliases (`/products`, `/outlets`).
- Dedicated `/tools/` endpoints for calculator, products, and outlets to enable direct integration tests.
- React/Vite frontend with chat bubbles, planner timeline, quick commands, and unhappy-flow indicators.
- FAISS-powered retrieval over ZUS drinkware catalogue; Text2SQL querying of outlet hours/services.
- Products tool optionally calls OpenRouter for a concise one‑sentence summary when an API key is provided; otherwise it falls back to a local summary.
- Automated coverage for happy-path, interrupted, and malicious interaction flows.

## Repository Layout

| Path | Purpose |
| --- | --- |
| `backend/` | FastAPI app, planner logic, tool integrations, and API wiring. |
| `frontend/` | React chat client with planner visualization components. |
| `db/` | SQLite databases, FAISS index artifacts, and schema migrations. |
| `scripts/` | Data ingestion (`ingest_products.py`, `sync_outlets.py`) and maintenance jobs. |
| `tests/` | Unit, integration, unhappy-flow, and Cypress E2E suites. |
| `docs/` | Diagrams, transcripts, planner write-up, and auxiliary documentation. |
| `prd.md` | Comprehensive product requirements document. |

## Prerequisites

- Python 3.11+
- Node.js 18+ and pnpm or npm
- Poetry or pip for Python dependency management
- `uvicorn`, `faiss-cpu`, `sqlite3`
- Optional: Docker (for containerized deployment) and Make (for convenience targets)

## Environment Variables

Create a `.env` file in `backend/` with the following keys (sample values shown):

```dotenv
OPENAI_API_KEY=sk-...
EMBEDDING_MODEL=text-embedding-3-large
SQLITE_PATH=../db/conversations.db
OUTLETS_DB_PATH=../db/outlets.db
FAISS_INDEX_PATH=../db/faiss/products.index
PRODUCTS_METADATA_PATH=../db/faiss/products_metadata.json
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=minimax/minimax-m2:free
OPENROUTER_REFERER=http://localhost:5173
OPENROUTER_TITLE=ZUS AI Assistant
OPENROUTER_RATE_LIMIT_PER_SEC=1.0
CALCULATOR_TIMEOUT_MS=2000
LOG_LEVEL=INFO
FRONTEND_ORIGIN=http://localhost:5173
```

For local-only mode you can omit `OPENAI_API_KEY` and configure `EMBEDDING_MODEL=all-MiniLM-L6-v2` (requires local sentence-transformers).

If `OPENROUTER_API_KEY` is unset the backend falls back to the built-in TF-IDF summary.

## Setup & Run Instructions

### 1. Clone and install dependencies

```bash
git clone https://github.com/<your-org>/mindhive-zus-assistant.git
cd mindhive-zus-assistant
```

#### Backend

```bash
cd backend
poetry install
poetry run uvicorn backend.main:app --reload --port 8000
```

#### Frontend

```bash
cd ../frontend
npm install
# or
pnpm install
```

### 2. Prepare data stores

```bash
cd scripts
python ingest_products.py --input-file ../docs/samples/products.sample.json
python sync_outlets.py --input-file ../docs/samples/outlets.sample.json --drop-existing
```

The product ingestion script tokenizes the catalogue, computes TF-IDF embeddings, and writes a
FAISS index (`db/faiss/products.index`) plus metadata with vocabulary/IDF weights. The outlets sync
script parameterizes SQL queries based on inferred locations and services.

> Both scripts expect local JSON exports. Sample files live in `docs/samples/` — duplicate and adjust
> them as needed, then rerun the scripts when you have updated data or live fetchers.

### Pull latest drinkware catalogue

1. Install scraper dependencies locally: `pip install -r scripts/requirements.txt`
2. Run the scraper on a machine with internet access:

   ```bash
   cd scripts
   python scrape_zus_drinkware.py --output ../db/raw/products.json
   ```

3. Regenerate the FAISS index:

   ```bash
   python ingest_products.py --input-file ../db/raw/products.json
   ```

4. Restart the backend so `ProductsTool` reloads the new embeddings.

### Refresh outlets database

1. With network access, run:

   ```bash
   cd scripts
    python scrape_zus_outlets.py --output ../docs/samples/outlets.sample.json --max-pages 22
   ```

2. Sync the SQLite store locally:

   ```bash
   python sync_outlets.py --input-file ../docs/samples/outlets.sample.json --drop-existing
   ```

3. Restart the backend so `OutletsTool` sees the updated database.

> Omit `--max-pages` to crawl until pagination is exhausted, or lower it for quicker smoke tests.

The ingestion commands populate:

- `db/faiss/products.index` — FAISS vector store built from drinkware catalogue.
- `db/outlets.db` — SQLite database with outlet metadata and hours.
- `db/conversations.db` — Created automatically on first backend run.

### 3. Run the backend

```bash
cd backend
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

The OpenAPI docs will be available at <http://localhost:8000/docs>.

### 4. Run the frontend

```bash
cd ../frontend
npm run dev  # defaults to http://localhost:5173
```

### 5. Execute the E2E experience

- Visit the frontend dev server, open the chat, and interact with `/calc`, `/products`, or `/outlets` commands.
- Toggle the planner timeline to verify tool selection, memory updates, and unhappy-flow handling.

## Architecture Overview

High-level diagrams are located in [`docs/diagrams`](docs/diagrams) and rendered via Mermaid in [`prd.md`](prd.md). They capture:

1. **Component Map** — User → Frontend → FastAPI gateway → Planner → Tool services (Calculator, Products RAG, Outlets Text2SQL) with FAISS and SQLite backing stores.
2. **Planner Sequence** — Request flow from user message through planner decisioning, tool invocation, memory update, and frontend telemetry.

![System Architecture](docs/diagrams/system-architecture.png)

![Planner Sequence](docs/diagrams/planner-sequence.png)

Exported diagrams (generate PNG/SVG locally if desired):
- `docs/diagrams/system-architecture.mmd` → `docs/diagrams/system-architecture.svg`
- `docs/diagrams/planner-sequence.mmd` → `docs/diagrams/planner-sequence.svg`

### Text2SQL Strategy

- The outlets tool (`backend/tools/outlets.py`) interprets natural language with keyword heuristics, normalises aliases (e.g., `ss2` → `SS 2`, `pj` → `Petaling Jaya`), and builds parameterised `LIKE` clauses; no raw SQL concatenation is performed.
- Outlet metadata lives in `db/outlets.db` with columns: `name`, `address`, `city`, `state`, `postcode`, `latitude`, `longitude`, `opening_hours`, `services`, and `map_url`. The sync script will recreate the table if the schema changes.
- When users request services (delivery/pickup/drive-thru) the tool filters on the `services` column; follow-up turns reuse the stored `location` slot, enabling multi-step Text2SQL flows.

## Key Trade-Offs

- **SQLite + FAISS (local)** keep deployment simple and self-contained for local-first workflows. For production scale you would migrate to managed SQL (e.g., Postgres) and a hosted vector DB (Pinecone, Weaviate, Qdrant).
- **Embeddings provider** defaults to OpenAI for accuracy but supports local sentence-transformer models for offline demos.
- **Planner policy** can run rule-based for deterministic grading or swap to LLM-guided heuristics in production; tests cover both modes.
- **Front-end stack** uses Vite/React over heavier app builders to satisfy the “no Streamlit/Gradio” constraint while remaining deployable on Vercel.

## Testing Strategy

| Suite | Command | Coverage |
| --- | --- | --- |
| Unit | `pytest tests/unit` | Tool utilities, planner reducers, memory helpers. |
| Integration | `pytest tests/integration` | `/chat`, `/calculator`, `/products`, `/outlets` API flows. |
| Coverage | `PYTHONPATH=.. poetry run pytest ../tests --cov=backend --cov-report=term-missing` | Aggregated backend coverage (also run in CI). |
| E2E | `npm run test:e2e` (Cypress) | Frontend chat, planner timeline, error banners, persistence. |

> Tip: Use `CYPRESS_BASE_URL` or `VITE_API_URL` to point Cypress to your running backend when executing E2E tests locally.

CI (GitHub Actions) runs all suites on pull requests and nightly schedules, publishing coverage and transcript artifacts.

## Screenshots & Gallery

The following screenshots and a short GIF demonstrate the end‑to‑end experience. Place your captures under `docs/screenshots/` using the suggested filenames below; the links will render automatically once the files exist:

- Chat: Outlets multi‑turn flow with planner timeline (GIF)
  - `![Outlets Flow](docs/screenshots/chat_outlets_flow.gif)`
- Chat: Calculator error handling (invalid input → friendly error)
  - `![Calculator Error](docs/screenshots/chat_calc_error.png)`
- Chat: Products RAG success (summary + top‑k)
  - `![Products Success](docs/screenshots/chat_products_success.png)`
- API Docs: OpenAPI UI at `/docs`
  - `![OpenAPI Docs](docs/screenshots/openapi_docs.png)`
- Readiness and Metrics endpoints
  - `![Readiness OK](docs/screenshots/ready_ok.png)`
  - `![Metrics Snapshot](docs/screenshots/metrics_snapshot.png)`

Tip: Keep the planner timeline visible in captures to illustrate intent/action decisions and missing‑slot prompts.

## Deployment Notes

### Backend (Railway / Render)

1. Set environment variables from `.env` (exclude local file-based paths if using mounted volumes).
2. Provision persistent storage for SQLite databases and FAISS index (e.g., Railway volume mounted at `/app/db`).
3. Use `uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}` as the start command.

### Frontend (Vercel / Netlify)

1. Configure environment variable `VITE_API_URL=https://<backend-domain>`.
2. Build command: `npm run build`; output dir: `dist`.
3. Ensure CORS allowed origins on the backend include the deployed frontend domain.

### Data Refresh

- Schedule GitHub Actions jobs (or cron) to run `scripts/ingest_products.py` and `scripts/sync_outlets.py`, committing updated artefacts or uploading to object storage.
- Monitor `/metrics` endpoint for latency, tool success rate, and planner confidence to detect drift.

## Documentation Bundle

- [`backend/openapi.yaml`](backend/openapi.yaml) — REST API specification for calculator, products, outlets, chat, and metrics endpoints. Regenerate from a running backend with `curl http://localhost:8000/openapi.json | yq -p json -o yaml > backend/openapi.yaml` (requires [yq](https://github.com/mikefarah/yq); alternatively pipe the JSON through `python -c "import json,yaml,sys; print(yaml.safe_dump(json.load(sys.stdin)))"`).
- [`docs/planner_decisions.md`](docs/planner_decisions.md) — Planner decision rationale and fallback logic.
- [`docs/transcripts/`](docs/transcripts) — Success and failure transcripts for representative conversation flows (see new additions: `products_unhappy.md`, `outlets_success.md`, `reset_flow.md`).
- [`docs/diagrams/`](docs/diagrams) — Mermaid sources for architecture visuals.
- [`prd.md`](prd.md) — Product requirements covering core capabilities, testing, and documentation deliverables.
