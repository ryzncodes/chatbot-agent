"""FastAPI application entry point for the ZUS AI Assistant backend."""

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import get_settings
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
tool_router = ToolRouter(
    {
        PlannerAction.CALL_CALCULATOR: CalculatorTool(),
        PlannerAction.CALL_PRODUCTS: ProductsTool(
            index_path=settings.faiss_index_path,
            metadata_path=settings.products_metadata_path,
        ),
        PlannerAction.CALL_OUTLETS: OutletsTool(settings.outlets_db_path),
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
