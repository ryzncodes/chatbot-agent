"""Base classes and types for executable tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping

from backend.memory.models import ConversationSnapshot, MessageTurn


@dataclass(slots=True)
class ToolContext:
    """Context provided to a tool invocation."""

    turn: MessageTurn
    conversation: ConversationSnapshot
    extras: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ToolResponse:
    """Standard tool response payload."""

    content: str
    data: dict[str, Any] = field(default_factory=dict)
    success: bool = True


class Tool(ABC):
    """Executable tool implementation interface."""

    name: str

    @abstractmethod
    async def run(self, context: ToolContext) -> ToolResponse:
        """Execute the tool given the provided context."""

    def describe(self) -> str:
        """Return a human-readable description for observability dashboards."""

        return self.__doc__ or self.name
