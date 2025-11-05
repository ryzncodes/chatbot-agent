# Backend

FastAPI service that orchestrates the planner, memory store, and tool integrations powering the ZUS AI Assistant.

## Quickstart

```bash
poetry install
poetry run uvicorn backend.main:app --reload --port 8000
```

The OpenAPI docs are exposed at `http://localhost:8000/docs`. Health checks live at `/health`, readiness at `/ready` (verifies SQLite + FAISS + outlets), and metrics at `/metrics`.

## Rate Limiting

An in-memory, per-process rate limiter is enabled by default to protect the API from bursts and abuse. Identity is derived from `X-User-ID` when present, otherwise the client IP (proxy-aware via `X-Forwarded-For`). The following environment variables control behavior (defaults shown):

- `RATE_LIMIT_ENABLED=true` — toggle limiter on/off.
- `RATE_LIMIT_UNAUTH_PER_MINUTE=60` — unauthenticated requests per minute per IP.
- `RATE_LIMIT_AUTH_PER_MINUTE=300` — authenticated requests per minute per user.
- `RATE_LIMIT_BURST_PER_SECOND=10` — short burst allowance per second.
- `RATE_LIMIT_INCLUDE_PATHS=["/chat"]` — only enforce on these paths. Supports `/*`. Leave empty to apply globally.
- `RATE_LIMIT_EXEMPT_PATHS=["/health","/metrics","/tools/*"]` — JSON list of paths to exempt. Supports suffix wildcard `/*` for prefix matches.

When the limit is exceeded, the API returns `429` with a JSON body:

```json
{
  "error": "rate_limit_exceeded",
  "message": "Too many requests. Please retry later.",
  "retry_after_seconds": 12
}
```

Headers include `Retry-After`, `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` (epoch seconds).

Note: This limiter is in-memory and enforces limits per worker process. For multi-instance deployments, consider a shared backend (e.g., Redis) and a distributed limiter.

Security: Client IP detection defaults to the connection peer address. Only set
`TRUST_X_FORWARDED_FOR=true` if you run behind a trusted reverse proxy that strips
or rewrites `X-Forwarded-For`.

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
