# Error Handling & Security Strategy

## Defensive Input Handling
- `/chat` validates `conversation_id` and `content` before processing, returning `400` for missing payloads to avoid empty turns (`tests/integration/test_chat_endpoint.py:27`).
- The planner falls back when intent confidence is low or required slots are missing, preventing premature tool calls (`backend/planner/simple.py:96`, `backend/main.py:240`).
- Calculator expressions are sanitized to allow only numeric characters and basic operators, rejecting forbidden tokens such as `__` or `pow` and bounding expression length (`backend/tools/calculator.py:17`).

## Tool Isolation & Failure Recovery
- Tool dispatch is wrapped in try/except so runtime failures surface as friendly messages while logging the exception (`backend/main.py:258`).
- Integration tests simulate dispatcher crashes to ensure the controller returns a recovery prompt without crashing (`tests/integration/test_chat_endpoint.py:72`).
- Products and outlets tools return structured `success=False` payloads when backing stores are missing, guiding users to retry later (`backend/tools/products.py:53`, `backend/tools/outlets.py:32`).

## Data Store Protection
- Text2SQL queries build parameterized LIKE clauses and never interpolate raw SQL fragments; malicious payloads fall back to empty results (`backend/tools/outlets.py:91`).
- Tests exercise an attempted SQL injection to confirm the endpoint stays resilient (`tests/integration/test_tools_routes.py:40`).
- The outlets ingestion script constructs the schema with known columns only, ensuring unknown fields are ignored (`scripts/sync_outlets.py:48`).

## Incident Visibility & Metrics
- Each planner decision increments counters by intent and action for observability (`backend/main.py:277`).
- Tool failures annotate responses with error hints for downstream logging (e.g., calculator error data shown in `docs/transcripts/calculator_failure.md:12`).

## Automated Coverage of Negative Scenarios
- Missing parameters: `/chat` and `/tools/products` return `400` when required inputs are absent (`tests/integration/test_chat_endpoint.py:27`, `tests/integration/test_tools_routes.py:14`).
- API downtime: mocked tool router failure produces a graceful apology (`tests/integration/test_chat_endpoint.py:72`).
- Malicious payloads: SQL injection attempt is neutralized with no data leakage (`tests/integration/test_tools_routes.py:40`).
