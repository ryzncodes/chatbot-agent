"""FastAPI application entry point for the ZUS AI Assistant backend."""

import logging
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.api.tools import create_tools_router
from backend.core.config import get_settings
from backend.core.errors import unhandled_exception_handler
from backend.core.logging import request_id_middleware
from backend.core.metrics import MetricsCollector
from backend.memory.models import MessageTurn
from backend.memory.store import SQLiteMemoryStore
from backend.planner.simple import RuleBasedPlanner
from backend.planner.types import PlannerAction, PlannerContext, PlannerDecision
from backend.tools.calculator import CalculatorTool
from backend.tools.outlets import OutletsTool
from backend.tools.products import ProductsTool
from backend.tools.router import ToolRouter

settings = get_settings()
memory_store = SQLiteMemoryStore(settings.sqlite_path)
planner = RuleBasedPlanner()
calculator_tool = CalculatorTool()
products_tool = ProductsTool(
    index_path=settings.faiss_index_path,
    metadata_path=settings.products_metadata_path,
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


def get_memory_store() -> SQLiteMemoryStore:
    """Dependency injector for the memory store."""

    return memory_store


@app.get("/conversations", tags=["conversations"])
async def list_conversations(store: SQLiteMemoryStore = Depends(get_memory_store)) -> list[str]:
    """List known conversation identifiers (development helper)."""

    return list(store.iter_conversations())


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

    if decision.slot_updates:
        store.upsert_slots(conversation_id, decision.slot_updates)

    response_content: str
    tool_success = False
    tool_data: dict | None = None

    if decision.action == PlannerAction.FINISH:
        store.reset(conversation_id)
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
        tool_response = await tool_router.dispatch(decision.action, turn, snapshot)
        response_content = tool_response.content if tool_response.success else "I'm still learning that."
        tool_success = tool_response.success
        tool_data = tool_response.data
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
    }


@app.on_event("startup")
async def configure_logging() -> None:
    level = getattr(logging, str(settings.log_level).upper(), logging.INFO)
    logging.basicConfig(level=level, format="%(levelname)s %(name)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)


app.add_exception_handler(Exception, unhandled_exception_handler)


@app.get("/metrics", tags=["metrics"])
async def metrics_endpoint() -> dict:
    snapshot = metrics.snapshot()
    return {
        "total_requests": snapshot.total_requests,
        "tool_calls": snapshot.tool_calls,
        "planner_intents": snapshot.planner_intents,
    }
