"""Simple arithmetic calculator tool."""

from __future__ import annotations

import math
from typing import Any

from backend.tools.base import Tool, ToolContext, ToolResponse


class CalculatorTool(Tool):
    """Evaluate basic arithmetic expressions with safety checks."""

    name = "calculator"

    allowed_chars = set("0123456789+-*/(). ")
    banned_sequences = {"__", "//", "**", "%", "abs", "pow", "sqrt"}

    async def run(self, context: ToolContext) -> ToolResponse:
        expression = context.turn.content.strip()
        sanitized = self._sanitize_expression(expression)

        try:
            result = self._evaluate(sanitized)
        except Exception as exc:  # noqa: BLE001 — surface error cleanly
            return ToolResponse(
                content="I couldn't compute that expression. Please check the syntax.",
                data={"error": str(exc)},
                success=False,
            )

        return ToolResponse(content=str(result), data={"expression": sanitized, "result": result})

    def _sanitize_expression(self, expression: str) -> str:
        for char in expression:
            if char not in self.allowed_chars:
                raise ValueError(f"Unsupported character: {char}")
        lowered = expression.lower()
        if any(seq in lowered for seq in self.banned_sequences):
            raise ValueError("Forbidden operator or keyword detected")
        if len(expression) > 128:
            raise ValueError("Expression too long")
        return expression

    def _evaluate(self, expression: str) -> Any:
        # Use eval in restricted namespace; for production replace with AST parser.
        allowed_names = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
        allowed_names.update({"__builtins__": {}})
        return eval(expression, allowed_names, {})
