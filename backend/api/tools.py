"""API routes for individual tool access."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.tools.calculator import CalculatorTool
from backend.tools.outlets import OutletsTool
from backend.tools.products import ProductsTool
from backend.tools.base import ToolContext
from backend.memory.models import ConversationSnapshot, MessageTurn


def create_tools_router(
    calculator: CalculatorTool,
    products: ProductsTool,
    outlets: OutletsTool,
) -> APIRouter:
    router = APIRouter(prefix="/tools", tags=["tools"])

    @router.post("/calculator")
    async def calculator_endpoint(payload: dict) -> dict:
        expression = payload.get("expression")
        if not expression:
            raise HTTPException(status_code=400, detail="expression is required")

        turn = MessageTurn(conversation_id="tool-calculator", role="user", content=expression)
        context = ToolContext(turn=turn, conversation=_empty_snapshot("tool-calculator"))
        result = await calculator.run(context)
        if not result.success:
            raise HTTPException(status_code=400, detail=result.content)
        return result.data | {"message": result.content}

    @router.get("/products")
    async def products_endpoint(query: str | None = None) -> dict:
        if not query:
            raise HTTPException(status_code=400, detail="query parameter is required")

        turn = MessageTurn(conversation_id="tool-products", role="user", content=query)
        context = ToolContext(turn=turn, conversation=_empty_snapshot("tool-products"))
        result = await products.run(context)
        if not result.success:
            raise HTTPException(status_code=404, detail=result.content)
        return {"message": result.content, "results": result.data.get("results", [])}

    @router.get("/outlets")
    async def outlets_endpoint(query: str | None = None) -> dict:
        if not query:
            raise HTTPException(status_code=400, detail="query parameter is required")

        turn = MessageTurn(conversation_id="tool-outlets", role="user", content=query)
        context = ToolContext(turn=turn, conversation=_empty_snapshot("tool-outlets"))
        result = await outlets.run(context)
        if not result.success:
            raise HTTPException(status_code=404, detail=result.content)
        return {"message": result.content, "results": result.data.get("results", [])}

    return router


def _empty_snapshot(conversation_id: str) -> ConversationSnapshot:
    return ConversationSnapshot(conversation_id=conversation_id, turns=[], slots={})
