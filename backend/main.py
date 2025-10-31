"""FastAPI application entry point for the ZUS AI Assistant backend."""

import logging
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
from pathlib import Path

from backend.api.tools import create_tools_router
from backend.core.config import get_settings
from backend.core.errors import unhandled_exception_handler
from backend.core.logging import request_id_middleware
from backend.core.metrics import MetricsCollector
from backend.memory.models import ConversationSnapshot, MessageTurn
from backend.memory.store import SQLiteMemoryStore
from backend.planner.simple import RuleBasedPlanner
from backend.planner.types import PlannerAction, PlannerContext, PlannerDecision
from backend.tools.base import ToolContext
from backend.tools.calculator import CalculatorTool
from backend.tools.outlets import OutletsTool
from backend.tools.products import ProductsTool
from backend.tools.router import ToolRouter

settings = get_settings()
logger = logging.getLogger("zus.app")

memory_store = SQLiteMemoryStore(settings.sqlite_path)
planner = RuleBasedPlanner()
calculator_tool = CalculatorTool()
products_tool = ProductsTool(
    index_path=settings.faiss_index_path,
    metadata_path=settings.products_metadata_path,
    openrouter_api_key=settings.openrouter_api_key,
    openrouter_model=settings.openrouter_model,
    openrouter_referer=settings.openrouter_referer,
    openrouter_title=settings.openrouter_title,
    openrouter_rate_limit_per_sec=settings.openrouter_rate_limit_per_sec,
)
outlets_tool = OutletsTool(settings.outlets_db_path)
metrics = MetricsCollector()
tool_router = ToolRouter(
    {
        PlannerAction.CALL_CALCULATOR: calculator_tool,
        PlannerAction.CALL_PRODUCTS: products_tool,
        PlannerAction.CALL_OUTLETS: outlets_tool,
    }
)
tool_logger = logging.getLogger("zus.tools")

app = FastAPI(title=settings.app_name, version="0.1.0", docs_url="/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.middleware("http")(request_id_middleware)

app.include_router(create_tools_router(calculator_tool, products_tool, outlets_tool))


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Return basic service status for monitoring."""

    return {"status": "ok"}


@app.get("/ready", tags=["health"])
async def readiness_probe() -> dict[str, Any]:
    """Readiness endpoint that verifies critical dependencies.

    Checks:
    - Conversations SQLite DB reachable and has expected tables.
    - Outlets SQLite DB exists and is queryable.
    - Products FAISS index and metadata present and loadable.
    """

    components: dict[str, dict[str, Any]] = {}

    # Conversations DB check
    conv_ok = False
    conv_error: str | None = None
    try:
        conv_path = Path(settings.sqlite_path)
        conv_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(conv_path) as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('messages','slots','conversations')"
            ).fetchone()
            conv_ok = row is not None
    except Exception as exc:  # noqa: BLE001
        conv_error = str(exc)
    components["conversations_db"] = {
        "path": str(settings.sqlite_path),
        "ok": conv_ok,
        **({"error": conv_error} if conv_error else {}),
    }

    # Outlets DB check
    outlets_ok = False
    outlets_error: str | None = None
    try:
        outlets_path = Path(settings.outlets_db_path)
        if outlets_path.exists():
            with sqlite3.connect(outlets_path) as conn:
                # Check table exists and is queryable
                conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='outlets'")
                conn.execute("SELECT 1 FROM outlets LIMIT 1")
                outlets_ok = True
        else:
            outlets_error = "database file not found"
    except Exception as exc:  # noqa: BLE001
        outlets_error = str(exc)
    components["outlets_db"] = {
        "path": str(settings.outlets_db_path),
        "ok": outlets_ok,
        **({"error": outlets_error} if outlets_error else {}),
    }

    # Products FAISS + metadata check
    products_ok = False
    products_error: str | None = None
    index_exists = Path(settings.faiss_index_path).exists()
    metadata_exists = Path(settings.products_metadata_path).exists()
    try:
        # Reuse tool internals to validate load
        index = products_tool._ensure_index()  # noqa: SLF001
        catalogue = products_tool._load_catalogue()  # noqa: SLF001
        products_ok = bool(index) and bool(catalogue)
        if not products_ok and index_exists and metadata_exists:
            products_error = "index/metadata present but failed to load"
    except Exception as exc:  # noqa: BLE001
        products_error = str(exc)
    components["products_store"] = {
        "index_path": str(settings.faiss_index_path),
        "metadata_path": str(settings.products_metadata_path),
        "index_exists": index_exists,
        "metadata_exists": metadata_exists,
        "ok": products_ok,
        **({"error": products_error} if products_error else {}),
    }

    overall = (
        "ok"
        if components["conversations_db"]["ok"] and components["outlets_db"]["ok"] and components["products_store"]["ok"]
        else (
            "degraded" if components["conversations_db"]["ok"] else "fail"
        )
    )

    return {
        "status": overall,
        "environment": settings.environment,
        "components": components,
    }


def get_memory_store() -> SQLiteMemoryStore:
    """Dependency injector for the memory store."""

    return memory_store


@app.get("/conversations", tags=["conversations"])
async def list_conversations(store: SQLiteMemoryStore = Depends(get_memory_store)) -> list[str]:
    """List known conversation identifiers (development helper)."""

    return list(store.iter_conversations())


@app.get("/products", tags=["tools"])
async def products_alias(query: str | None = None) -> dict[str, Any]:
    """Alias endpoint providing product results for compatibility with legacy clients."""

    if not query:
        raise HTTPException(status_code=400, detail="query parameter is required")

    snapshot = ConversationSnapshot(conversation_id="alias-products", turns=[], slots={})
    turn = MessageTurn(conversation_id="alias-products", role="user", content=query)
    context = ToolContext(turn=turn, conversation=snapshot)

    result = await products_tool.run(context)
    if not result.success:
        raise HTTPException(status_code=404, detail=result.content)

    return {
        "message": result.content,
        "results": result.data.get("results", []),
    }


@app.post("/chat", tags=["chat"])
async def chat(message: dict, store: SQLiteMemoryStore = Depends(get_memory_store)) -> dict:
    """Primary chat endpoint orchestrating planner and tools."""

    conversation_id = message.get("conversation_id")
    role = message.get("role", "user")
    content = message.get("content")

    if not conversation_id or not content:
        raise HTTPException(status_code=400, detail="conversation_id and content are required")

    turn = MessageTurn(conversation_id=conversation_id, role=role, content=content)
    store.append_turn(turn)

    snapshot = store.load_snapshot(conversation_id)
    planner_context = PlannerContext(turn=turn, conversation=snapshot)
    decision: PlannerDecision = planner.decide(planner_context)

    slot_state = dict(snapshot.slots)

    if decision.action == PlannerAction.FINISH:
        store.reset(conversation_id)
        slot_state.clear()
    elif decision.slot_updates:
        store.upsert_slots(conversation_id, decision.slot_updates)
        slot_state.update(decision.slot_updates)

    response_content: str
    tool_success = False
    tool_data: dict | None = None

    if decision.action == PlannerAction.FINISH:
        response_content = "Conversation reset. How else can I assist you?"
        tool_success = True
        tool_data = {}
    elif decision.action == PlannerAction.ASK_FOLLOW_UP:
        missing = [slot.replace("_", " ") for slot, satisfied in decision.required_slots.items() if not satisfied]
        response_content = (
            f"Could you share the {missing[0]}?" if missing else "Could you provide a bit more detail?"
        )
        tool_success = True
        tool_data = {"missing_slots": missing}
    elif decision.action == PlannerAction.FALLBACK:
        response_content = "I didn't quite catch that. Could you rephrase or give more details?"
        tool_success = False
        tool_data = {}
    elif tool_router.supports(decision.action):
        try:
            tool_response = await tool_router.dispatch(decision.action, turn, snapshot)
            response_content = tool_response.content if tool_response.success else "I'm still learning that."
            tool_success = tool_response.success
            tool_data = tool_response.data
        except Exception as exc:  # noqa: BLE001
            tool_logger.exception("Tool dispatch failed", extra={"action": decision.action.value})
            response_content = "I ran into an issue calling that tool. Could you try again later?"
            tool_success = False
            tool_data = {"error": str(exc)}
    else:
        response_content = "That capability isn't available yet, but I'm taking note."
        tool_success = False
        tool_data = {}

    metrics.record_request(decision.intent.value, decision.action.value)

    return {
        "conversation_id": conversation_id,
        "intent": decision.intent.value,
        "action": decision.action.value,
        "confidence": decision.confidence,
        "tool_success": tool_success,
        "message": response_content,
        "tool_data": tool_data or {},
        "required_slots": decision.required_slots,
        "slots": {key: str(value) for key, value in slot_state.items() if value is not None},
    }


@app.on_event("startup")
async def configure_logging() -> None:
    level = getattr(logging, str(settings.log_level).upper(), logging.INFO)
    logging.basicConfig(level=level, format="%(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logger.info("Logging configured at %s level for %s environment", logging.getLevelName(level), settings.environment)


app.add_exception_handler(Exception, unhandled_exception_handler)


@app.get("/metrics", tags=["metrics"])
async def metrics_endpoint() -> dict:
    snapshot = metrics.snapshot()
    return {
        "total_requests": snapshot.total_requests,
        "tool_calls": snapshot.tool_calls,
        "planner_intents": snapshot.planner_intents,
    }
