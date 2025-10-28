"""Baseline rule-based planner implementation."""

from __future__ import annotations

from typing import Any

from backend.planner.base import Planner
from backend.planner.types import Intent, PlannerAction, PlannerContext, PlannerDecision


class RuleBasedPlanner(Planner):
    """Lightweight intent classifier with deterministic slot requirements."""

    def describe(self) -> str:
        return "Rule-based keyword planner"

    def decide(self, context: PlannerContext) -> PlannerDecision:
        message = context.turn.content.lower()
        intent = self._classify_intent(message)
        required_slots = self._derive_slots(intent, context)

        action = self._select_action(intent, required_slots)
        confidence = 0.65 if intent is Intent.UNKNOWN else 0.9

        return PlannerDecision(
            intent=intent,
            action=action,
            confidence=confidence,
            required_slots=required_slots,
        )

    def _classify_intent(self, message: str) -> Intent:
        if any(keyword in message for keyword in ["calc", "sum", "add", "minus", "+", "-"]):
            return Intent.CALCULATE
        if any(keyword in message for keyword in ["product", "drink", "tumbler", "merch"]):
            return Intent.PRODUCT_INFO
        if any(keyword in message for keyword in ["outlet", "store", "open", "closing", "hours"]):
            return Intent.OUTLET_INFO
        if "reset" in message:
            return Intent.RESET
        if any(keyword in message for keyword in ["hello", "hi", "thanks", "help"]):
            return Intent.SMALL_TALK
        return Intent.UNKNOWN

    def _derive_slots(self, intent: Intent, context: PlannerContext) -> dict[str, bool]:
        slots_required: dict[str, bool] = {
            "topic": intent in {Intent.PRODUCT_INFO, Intent.OUTLET_INFO},
            "operation": intent is Intent.CALCULATE,
            "location": intent is Intent.OUTLET_INFO,
            "product_type": intent is Intent.PRODUCT_INFO,
        }

        # Mark slots satisfied if already present in memory
        for slot, required in slots_required.items():
            if not required:
                continue
            slots_required[slot] = slot in context.conversation.slots

        return slots_required

    def _select_action(self, intent: Intent, slots: dict[str, bool]) -> PlannerAction:
        if intent is Intent.CALCULATE and slots.get("operation", False):
            return PlannerAction.CALL_CALCULATOR
        if intent is Intent.PRODUCT_INFO and slots.get("product_type", False):
            return PlannerAction.CALL_PRODUCTS
        if intent is Intent.OUTLET_INFO and slots.get("location", False):
            return PlannerAction.CALL_OUTLETS
        if intent is Intent.RESET:
            return PlannerAction.FINISH
        if intent in {Intent.UNKNOWN, Intent.SMALL_TALK}:
            return PlannerAction.FALLBACK
        return PlannerAction.ASK_FOLLOW_UP
