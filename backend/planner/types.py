"""Planner-related enums and data structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, MutableMapping

from backend.memory.models import ConversationSnapshot, MessageTurn


class Intent(str, Enum):
    """Supported high-level intents."""

    CALCULATE = "calculate"
    PRODUCT_INFO = "product_info"
    OUTLET_INFO = "outlet_info"
    SMALL_TALK = "small_talk"
    RESET = "reset"
    UNKNOWN = "unknown"


class PlannerAction(str, Enum):
    """Available planner actions."""

    ASK_FOLLOW_UP = "ask_follow_up"
    CALL_CALCULATOR = "call_calculator"
    CALL_PRODUCTS = "call_products"
    CALL_OUTLETS = "call_outlets"
    FALLBACK = "fallback"
    FINISH = "finish"
    SMALL_TALK = "small_talk"


@dataclass(slots=True)
class PlannerContext:
    """Inputs passed to the planner when deciding next action."""

    turn: MessageTurn
    conversation: ConversationSnapshot
    params: MutableMapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PlannerDecision:
    """Planner output describing chosen action and metadata."""

    intent: Intent
    action: PlannerAction
    confidence: float
    required_slots: Mapping[str, bool]
    slot_updates: dict[str, Any] = field(default_factory=dict)
    payload: dict[str, Any] = field(default_factory=dict)
