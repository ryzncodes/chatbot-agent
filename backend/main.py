"""FastAPI application entry point for the ZUS AI Assistant backend."""

from fastapi import FastAPI

app = FastAPI(title="ZUS AI Assistant", version="0.1.0")


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    """Return basic service status for monitoring."""
    return {"status": "ok"}
