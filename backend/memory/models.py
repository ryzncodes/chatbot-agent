"""Dataclasses representing conversation turns and memory state."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TypedDict


class SlotState(TypedDict, total=False):
    """Represents tracked slot values for a conversation."""

    topic: str
    operation: str
    location: str
    time_range: str
    product_type: str
    loyalty_status: str


@dataclass(slots=True)
class MessageTurn:
    """Single conversational turn stored in memory."""

    conversation_id: str
    role: str
    content: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ConversationSnapshot:
    """Aggregated view of a conversation with slot state."""

    conversation_id: str
    turns: list[MessageTurn]
    slots: SlotState
