"""Tool router mapping planner actions to tool implementations."""

from __future__ import annotations

from typing import Mapping

from backend.memory.models import ConversationSnapshot, MessageTurn
from backend.planner.types import PlannerAction
from backend.tools.base import Tool, ToolContext, ToolResponse


class ToolRouter:
    """Dispatch planner actions to concrete tools."""

    def __init__(self, tools: Mapping[PlannerAction, Tool]) -> None:
        self._tools = tools

    def supports(self, action: PlannerAction) -> bool:
        return action in self._tools

    async def dispatch(
        self,
        action: PlannerAction,
        turn: MessageTurn,
        conversation: ConversationSnapshot,
        extras: dict | None = None,
    ) -> ToolResponse:
        tool = self._tools[action]

        context = ToolContext(turn=turn, conversation=conversation, extras=extras or {})
        return await tool.run(context)
