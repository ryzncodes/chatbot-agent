# Backend

FastAPI service that orchestrates the planner, memory store, and tool integrations powering the ZUS AI Assistant.

## Quickstart

```bash
poetry install
poetry run uvicorn backend.main:app --reload --port 8000
```

The OpenAPI docs are exposed at `http://localhost:8000/docs`. Health checks live at `/health`, readiness at `/ready` (verifies SQLite + FAISS + outlets), and metrics at `/metrics`.

## Key Modules

- `backend/main.py` — application initialization, dependency wiring, and HTTP routes.
- `backend/planner/` — rule-based planner implementation and supporting types.
- `backend/tools/` — calculator, product retrieval, and outlet lookup tools.
- `backend/memory/` — SQLite-backed conversation store and data models.
- `backend/api/tools.py` — explicit tool endpoints used for diagnostics and tests.

## Testing

Run the full backend suite with:

```bash
poetry run pytest
```

Target specific suites via `pytest tests/unit` or `pytest tests/integration`. Use `poetry run pytest --cov=backend` to inspect coverage.
