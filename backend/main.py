"""FastAPI application entry point for the ZUS AI Assistant backend."""

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import get_settings
from backend.memory.store import SQLiteMemoryStore
from backend.memory.models import MessageTurn
from backend.planner.simple import RuleBasedPlanner
from backend.planner.types import PlannerContext, PlannerDecision, PlannerAction
from backend.tools.calculator import CalculatorTool
from backend.tools.router import ToolRouter

settings = get_settings()
memory_store = SQLiteMemoryStore(settings.sqlite_path)
planner = RuleBasedPlanner()
tool_router = ToolRouter(
    {
        PlannerAction.CALL_CALCULATOR: CalculatorTool(),
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

    tool_response = await tool_router.dispatch(decision.action, turn, snapshot)

    response_content = tool_response.content if tool_response.success else "I'm still learning that."
    return {
        "conversation_id": conversation_id,
        "intent": decision.intent.value,
        "action": decision.action.value,
        "confidence": decision.confidence,
        "tool_success": tool_response.success,
        "message": response_content,
        "tool_data": tool_response.data,
        "required_slots": decision.required_slots,
    }
