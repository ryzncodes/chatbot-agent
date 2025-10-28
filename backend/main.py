"""FastAPI application entry point for the ZUS AI Assistant backend."""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import get_settings
from backend.memory.store import SQLiteMemoryStore

settings = get_settings()
memory_store = SQLiteMemoryStore(settings.sqlite_path)

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
